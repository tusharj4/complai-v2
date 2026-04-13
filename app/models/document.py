from sqlalchemy import Column, String, JSON, DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime, timezone
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Uuid, primary_key=True, default=uuid4)
    company_id = Column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    source = Column(Enum("scraper", "upload", "manual", name="document_source"), nullable=False)
    document_type = Column(Enum("gst_return", "itr", "mca_filing", "bank_statement", name="document_type_enum"), nullable=False)
    s3_path = Column(String(512), nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    extraction_status = Column(
        Enum("pending", "extracted", "classified", "failed", name="extraction_status_enum"),
        default="pending",
        index=True,
    )
    error_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="documents")
    classifications = relationship("Classification", back_populates="document")
    extractions = relationship("ExtractionCache", back_populates="document")
