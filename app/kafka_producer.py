"""
Kafka event producer for CompLai compliance events.
Publishes events to topics for real-time updates and webhooks.
Falls back gracefully when Kafka is unavailable (dev mode).
"""

import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=[settings.KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=3,
            acks="all",
        )
        logger.info("Kafka producer connected")
        return _producer
    except Exception as e:
        logger.warning(f"Kafka unavailable, events will be logged only: {e}")
        return None


def publish_event(topic: str, event: dict):
    """Publish event to Kafka topic. Falls back to logging if Kafka unavailable."""
    producer = _get_producer()
    if producer:
        try:
            producer.send(topic, event)
            producer.flush(timeout=5)
            logger.info(f"Event published to {topic}: {event.get('event_type', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to publish to Kafka: {e}")
    else:
        logger.info(f"[EVENT] {topic}: {json.dumps(event)}")


# Standard topics
TOPIC_COMPLIANCE_UPDATES = "compliance_updates"
TOPIC_AUDIT_EVENTS = "audit_events"
TOPIC_SCRAPER_EVENTS = "scraper_events"
