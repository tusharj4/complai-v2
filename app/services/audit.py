import logging
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import AuditLog

logger = logging.getLogger(__name__)


def log_event(
    db: Session,
    company_id: str,
    event_type: str,
    details: dict,
    document_id: str = None,
    user_id: str = None,
) -> AuditLog:
    """
    Create an immutable audit log entry.
    All significant events (scrape, extract, classify, override) get logged here.
    """
    log_entry = AuditLog(
        company_id=UUID(company_id) if isinstance(company_id, str) else company_id,
        document_id=UUID(document_id) if isinstance(document_id, str) else document_id,
        event_type=event_type,
        details=details,
        created_by_user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    logger.info(
        f"AUDIT: {event_type} | company={company_id} | doc={document_id}",
        extra={
            "company_id": str(company_id),
            "document_id": str(document_id) if document_id else None,
            "event_type": event_type,
        },
    )

    return log_entry
