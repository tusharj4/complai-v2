from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime, timezone
from app.database import Base


class Classification(Base):
    __tablename__ = "classifications"

    id = Column(Uuid, primary_key=True, default=uuid4)
    document_id = Column(Uuid, ForeignKey("documents.id"), nullable=False, index=True)
    scraper_version = Column(String(64), nullable=False)
    model_version = Column(String(64), nullable=False)
    classification = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    document = relationship("Document", back_populates="classifications")
