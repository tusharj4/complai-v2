from sqlalchemy import Column, String, JSON, DateTime, Uuid
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime, timezone
from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Uuid, primary_key=True, default=uuid4)
    partner_id = Column(Uuid, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    gst_id = Column(String(15), unique=True, nullable=False, index=True)
    filing_deadlines = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    documents = relationship("Document", back_populates="company")
    audit_logs = relationship("AuditLog", back_populates="company")
