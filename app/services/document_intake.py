import hashlib
import logging
from uuid import uuid4, UUID
from enum import Enum
from sqlalchemy.orm import Session
from app.models import Document

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50_000_000  # 50MB


class DocumentSource(str, Enum):
    SCRAPER = "scraper"
    UPLOAD = "upload"
    MANUAL = "manual"


class DocumentType(str, Enum):
    GST_RETURN = "gst_return"
    ITR = "itr"
    MCA_FILING = "mca_filing"
    BANK_STATEMENT = "bank_statement"


def intake_document(
    db: Session,
    company_id: str,
    source: str,
    document_type: str,
    content: bytes,
    metadata: dict = None,
    s3_client=None,
) -> Document:
    """
    Process incoming document:
    1. Validate size
    2. Deduplicate by content hash
    3. Store to S3 (or local for dev)
    4. Create document record
    5. Queue extraction task
    """
    # Validate size
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large ({len(content)} bytes). Max: {MAX_FILE_SIZE} bytes")

    # Deduplicate
    content_hash = hashlib.sha256(content).hexdigest()
    existing = db.query(Document).filter(Document.content_hash == content_hash).first()
    if existing:
        logger.info(f"Document already exists (hash match): {existing.id}")
        return existing

    # Determine S3 path
    s3_key = f"documents/{company_id}/{document_type}/{uuid4()}.pdf"

    # Store to S3 if client available
    if s3_client:
        s3_client.put_object(
            Bucket="complai-documents",
            Key=s3_key,
            Body=content,
            ServerSideEncryption="AES256",
        )

    # Create document record
    doc = Document(
        company_id=UUID(company_id) if isinstance(company_id, str) else company_id,
        source=source,
        document_type=document_type,
        s3_path=s3_key,
        content_hash=content_hash,
        metadata_=metadata or {},
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Queue extraction task
    from app.tasks.workers import extract_and_classify
    try:
        extract_and_classify.apply_async(args=[str(doc.id)])
    except Exception as e:
        logger.warning(f"Could not queue extraction task: {e}")

    logger.info(f"Document ingested: {doc.id} ({document_type})")
    return doc
