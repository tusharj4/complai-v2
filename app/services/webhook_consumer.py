"""
Kafka Webhook Consumer (Task 4.1.3)

Listens to Kafka topics and dispatches events to registered WebhookEndpoint URLs.

Usage (runs as a separate process or Celery beat task):
    python -m app.services.webhook_consumer

Features:
- HMAC-SHA256 request signing (when webhook has a secret)
- Retry with exponential backoff (up to 3 attempts)
- Per-delivery audit trail in the database
- Graceful shutdown on SIGTERM/SIGINT
"""

import hashlib
import hmac
import json
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Topics to consume from
WEBHOOK_TOPICS = [
    "compliance_updates",
    "audit_events",
    "scraper_events",
]

MAX_DELIVERY_RETRIES = 3
RETRY_DELAYS = [5, 30, 120]  # seconds between attempts
DELIVERY_TIMEOUT = 10  # seconds per HTTP request


def dispatch_webhook(
    url: str,
    payload: dict,
    headers: dict,
    secret: Optional[str] = None,
    timeout: int = DELIVERY_TIMEOUT,
) -> dict:
    """
    POST payload to webhook URL.
    Signs the request with HMAC-SHA256 if secret is provided.

    Returns:
        {"success": bool, "status_code": int|None, "error": str|None}
    """
    body = json.dumps(payload, default=str)

    delivery_headers = {
        "Content-Type": "application/json",
        "User-Agent": "CompLai-Webhook/2.0",
        "X-CompLai-Event": payload.get("event_type", "unknown"),
        "X-CompLai-Delivery-At": datetime.now(timezone.utc).isoformat(),
        **headers,
    }

    # HMAC-SHA256 signing
    if secret:
        signature = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        delivery_headers["X-CompLai-Signature"] = f"sha256={signature}"

    for attempt in range(MAX_DELIVERY_RETRIES):
        try:
            response = requests.post(
                url,
                data=body,
                headers=delivery_headers,
                timeout=timeout,
            )

            if response.status_code < 500:
                # 2xx = success, 4xx = partner misconfiguration (don't retry)
                return {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "error": None if response.status_code < 400 else f"Client error: {response.status_code}",
                }
            else:
                logger.warning(
                    f"Webhook delivery attempt {attempt+1} got {response.status_code} from {url}"
                )

        except requests.Timeout:
            logger.warning(f"Webhook delivery attempt {attempt+1} timed out: {url}")
        except requests.ConnectionError as e:
            logger.warning(f"Webhook delivery attempt {attempt+1} connection error: {e}")
        except Exception as e:
            logger.error(f"Webhook delivery attempt {attempt+1} unexpected error: {e}")

        # Exponential backoff before retry (skip on last attempt)
        if attempt < MAX_DELIVERY_RETRIES - 1:
            delay = RETRY_DELAYS[attempt]
            logger.info(f"Retrying webhook delivery in {delay}s...")
            time.sleep(delay)

    return {
        "success": False,
        "status_code": None,
        "error": f"All {MAX_DELIVERY_RETRIES} delivery attempts failed",
    }


def _deliver_to_webhooks(event: dict, db) -> None:
    """Find matching webhooks and deliver the event."""
    from app.models import WebhookEndpoint

    company_id = event.get("company_id")
    event_type = event.get("event_type", "unknown")

    # Query: partner's webhooks matching this company + event type
    webhooks = (
        db.query(WebhookEndpoint)
        .filter(
            WebhookEndpoint.is_active == True,
        )
        .all()
    )

    matching = [
        wh for wh in webhooks
        if wh.matches_event(event_type)
        and (wh.company_id is None or str(wh.company_id) == company_id)
    ]

    logger.info(f"Dispatching event '{event_type}' to {len(matching)} webhook(s)")

    for webhook in matching:
        result = dispatch_webhook(
            url=webhook.url,
            payload=event,
            headers=webhook.headers or {},
            secret=webhook.secret,
        )

        # Update delivery stats
        try:
            webhook.last_delivery_at = datetime.now(timezone.utc)
            webhook.last_delivery_status = "success" if result["success"] else "failed"
            # Increment counter
            current = int(webhook.total_deliveries or "0")
            webhook.total_deliveries = str(current + 1)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update webhook stats: {e}")

        if result["success"]:
            logger.info(f"Webhook delivered to {webhook.url} (HTTP {result['status_code']})")
        else:
            logger.error(f"Webhook delivery failed to {webhook.url}: {result['error']}")


class WebhookConsumer:
    """
    Kafka consumer that dispatches events to registered webhooks.
    Runs as a long-lived background process.
    """

    def __init__(self):
        self._running = False
        self._consumer = None

        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("Webhook consumer shutting down...")
        self._running = False
        if self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass

    def _init_consumer(self):
        """Lazy-initialize Kafka consumer with graceful fallback."""
        try:
            from kafka import KafkaConsumer
            from app.config import settings

            self._consumer = KafkaConsumer(
                *WEBHOOK_TOPICS,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                group_id="webhook-dispatcher",
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=5000,  # Allow periodic shutdown checks
                max_poll_records=50,
            )
            logger.info(f"Webhook consumer connected to Kafka, topics: {WEBHOOK_TOPICS}")
            return True
        except Exception as e:
            logger.warning(f"Kafka unavailable, webhook consumer will not start: {e}")
            return False

    def run(self):
        """Main consumer loop."""
        from app.database import SessionLocal

        if not self._init_consumer():
            logger.info("Exiting webhook consumer (Kafka not available)")
            return

        self._running = True
        logger.info("Webhook consumer started")

        while self._running:
            try:
                for message in self._consumer:
                    if not self._running:
                        break

                    event = message.value
                    logger.debug(f"Received event from topic {message.topic}: {event.get('event_type')}")

                    db = SessionLocal()
                    try:
                        _deliver_to_webhooks(event, db)
                    except Exception as e:
                        logger.error(f"Error processing webhook event: {e}")
                    finally:
                        db.close()

            except Exception as e:
                if self._running:
                    logger.error(f"Consumer loop error: {e}")
                    time.sleep(5)  # Brief pause before restarting

        logger.info("Webhook consumer stopped")


def run_consumer():
    """Entry point for running the consumer as a script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    consumer = WebhookConsumer()
    consumer.run()


if __name__ == "__main__":
    run_consumer()
