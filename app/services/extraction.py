import io
import logging
from sqlalchemy.orm import Session
from app.models import Document, ExtractionCache

logger = logging.getLogger(__name__)


def is_scanned_pdf(content: bytes) -> bool:
    """Check if PDF is scanned (no selectable text) vs native."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return len(text.strip()) < 100
    except ImportError:
        # Fallback: try PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text = "".join(page.extract_text() or "" for page in reader.pages)
            return len(text.strip()) < 100
        except Exception:
            return True
    except Exception:
        return True


def extract_text_native(content: bytes) -> str:
    """Extract text from native (non-scanned) PDF."""
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        texts = []
        for page_num, page in enumerate(doc):
            texts.append(f"--- PAGE {page_num + 1} ---\n{page.get_text()}")
        doc.close()
        return "\n".join(texts)
    except ImportError:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(content))
        texts = []
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            texts.append(f"--- PAGE {page_num + 1} ---\n{text}")
        return "\n".join(texts)


def extract_text_ocr(content: bytes) -> str:
    """OCR a scanned PDF using Tesseract."""
    import pytesseract
    from pdf2image import convert_from_bytes

    images = convert_from_bytes(content, dpi=300)
    texts = []
    for page_num, image in enumerate(images):
        text = pytesseract.image_to_string(image, lang="eng+hin")
        texts.append(f"--- PAGE {page_num + 1} ---\n{text}")

    return "\n".join(texts)


def extract_document(document_id: str, db: Session, s3_client=None) -> str:
    """
    Extract text from a document, using cache if available.
    Routes to OCR or native extraction as appropriate.
    """
    # Check cache first
    cached = db.query(ExtractionCache).filter(
        ExtractionCache.document_id == document_id
    ).first()
    if cached:
        logger.info(f"Using cached extraction for {document_id}")
        return cached.extracted_text

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    # Fetch content from S3 or use metadata for scraped docs
    content = None
    if s3_client:
        try:
            s3_obj = s3_client.get_object(Bucket="complai-documents", Key=doc.s3_path)
            content = s3_obj["Body"].read()
        except Exception as e:
            logger.warning(f"S3 fetch failed for {document_id}: {e}")

    # For scraped documents, content is already structured in metadata
    if content is None and doc.source == "scraper":
        import json
        full_text = json.dumps(doc.metadata_, indent=2) if doc.metadata_ else ""
        logger.info(f"Using metadata as text for scraped doc {document_id}")
    elif content:
        # Choose extraction path based on PDF type
        if is_scanned_pdf(content):
            logger.info(f"OCR extraction for scanned PDF {document_id}")
            full_text = extract_text_ocr(content)
        else:
            logger.info(f"Native extraction for PDF {document_id}")
            full_text = extract_text_native(content)
    else:
        full_text = ""

    # Cache result
    if full_text:
        cache = ExtractionCache(
            document_id=document_id,
            extracted_text=full_text,
            s3_path=f"extractions/{document_id}/text.txt",
            char_count=len(full_text),
        )
        db.add(cache)
        db.commit()

    logger.info(f"Extracted {len(full_text)} chars from {document_id}")
    return full_text
