"""
WebhookEndpoint model — stores partner webhook registrations.

Partners register a URL per company to receive real-time compliance events.
The Kafka consumer reads from compliance_updates topic and POSTs to matching webhooks.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, Boolean, JSON, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy import Uuid
from app.database import Base


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    company_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,  # None = global webhook for all partner companies
        index=True,
    )

    # Endpoint configuration
    url = Column(String(2048), nullable=False)
    event_types = Column(JSON, nullable=False, default=list)  # ["compliance_check_complete", "manual_override", ...]
    headers = Column(JSON, nullable=False, default=dict)      # Custom headers (e.g. {"X-API-Key": "..."})
    secret = Column(String(255), nullable=True)               # HMAC-SHA256 signing secret
    is_active = Column(Boolean, default=True, nullable=False)

    # Delivery statistics
    total_deliveries = Column(String(20), default="0")        # Stored as string to avoid migration issues
    last_delivery_at = Column(DateTime(timezone=True), nullable=True)
    last_delivery_status = Column(String(50), nullable=True)  # "success" / "failed"

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    company = relationship("Company", back_populates=None)

    __table_args__ = (
        Index("idx_webhook_partner_active", "partner_id", "is_active"),
        Index("idx_webhook_company", "company_id", "is_active"),
    )

    def matches_event(self, event_type: str) -> bool:
        """Check if this webhook should receive a given event type."""
        if not self.is_active:
            return False
        return "*" in (self.event_types or []) or event_type in (self.event_types or [])
