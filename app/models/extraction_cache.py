from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime, timezone
from app.database import Base


class ExtractionCache(Base):
    __tablename__ = "extraction_cache"

    id = Column(Uuid, primary_key=True, default=uuid4)
    document_id = Column(Uuid, ForeignKey("documents.id"), nullable=False, unique=True)
    extracted_text = Column(Text, nullable=False)
    s3_path = Column(String(512), nullable=False)
    char_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="extractions")
