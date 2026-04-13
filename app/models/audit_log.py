from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime, timezone
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Uuid, primary_key=True, default=uuid4)
    company_id = Column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    document_id = Column(Uuid, ForeignKey("documents.id"), nullable=True)
    event_type = Column(String(64), nullable=False, index=True)
    details = Column(JSON, nullable=False)
    created_by_user_id = Column(Uuid, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    company = relationship("Company", back_populates="audit_logs")
