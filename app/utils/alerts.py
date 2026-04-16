"""
Alerting utility for CompLai.
Sends alerts to logging/Datadog and optionally Slack for critical issues.
"""

import logging

logger = logging.getLogger(__name__)


def send_alert(severity: str, message: str, company_id: str = None, extra: dict = None):
    """
    Send alert based on severity level.
    - info: log only
    - warning: log + Datadog metric
    - error: log + Datadog metric
    - critical: log + Datadog metric + Slack notification
    """
    log_extra = {"company_id": company_id, **(extra or {})}

    level = getattr(logging, severity.upper(), logging.ERROR)
    logger.log(level, f"ALERT [{severity.upper()}]: {message}", extra=log_extra)

    # Datadog metric (if configured)
    try:
        from datadog import statsd
        statsd.increment("complai.alerts", tags=[f"severity:{severity}", f"company:{company_id or 'global'}"])
    except Exception:
        pass

    # Slack for critical alerts
    if severity == "critical":
        _send_slack_alert(message, company_id)


def _send_slack_alert(message: str, company_id: str = None):
    """Send critical alert to Slack #complai-alerts channel."""
    try:
        # Slack webhook integration (configure SLACK_WEBHOOK_URL in .env)
        from app.config import settings
        import requests

        webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", None)
        if webhook_url:
            payload = {
                "channel": "#complai-alerts",
                "text": f":rotating_light: *CRITICAL*: {message}\nCompany: {company_id or 'N/A'}",
            }
            requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
