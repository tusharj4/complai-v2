import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def extract_and_classify(self, document_id: str):
    """Extract text from document and queue classification."""
    from app.database import SessionLocal
    from app.models import Document
    from app.services.extraction import extract_document
    from app.services.audit import log_event

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # Extract text
        extracted_text = extract_document(document_id, db)

        # Update status
        doc.extraction_status = "extracted"
        db.commit()

        # Queue classification
        classify_document.apply_async(args=[document_id])

        log_event(
            db=db,
            company_id=str(doc.company_id),
            event_type="extraction_complete",
            document_id=document_id,
            details={"char_count": len(extracted_text)},
        )

        return {"document_id": document_id, "status": "extracted", "char_count": len(extracted_text)}

    except Exception as exc:
        logger.error(f"Extraction failed for {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def classify_document(self, document_id: str):
    """Classify an extracted document using ML model or rule-based fallback."""
    from app.database import SessionLocal
    from app.models import Document, Classification, ExtractionCache
    from app.services.classification import classify_document_text
    from app.services.audit import log_event

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # Get extracted text
        cache = db.query(ExtractionCache).filter(
            ExtractionCache.document_id == document_id
        ).first()

        if not cache:
            # For scraped docs, use metadata as text
            import json
            text = json.dumps(doc.metadata_, indent=2) if doc.metadata_ else ""
        else:
            text = cache.extracted_text

        if not text:
            raise ValueError(f"No text available for {document_id}")

        # Classify
        result = classify_document_text(text, {"document_type": doc.document_type})

        # Store classification
        classification = Classification(
            document_id=document_id,
            scraper_version=doc.metadata_.get("scraper_version", "unknown") if doc.metadata_ else "unknown",
            model_version=result["model_version"],
            classification=result,
        )
        db.add(classification)

        # Update document status
        doc.extraction_status = "classified"
        db.commit()

        # Audit log
        log_event(
            db=db,
            company_id=str(doc.company_id),
            event_type="classification",
            document_id=document_id,
            details=result,
        )

        logger.info(f"Classified {document_id}: {result['status']} (confidence {result['confidence']:.2f})")
        return result

    except Exception as exc:
        logger.error(f"Classification failed for {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def scrape_portal(self, company_id: str, portal: str):
    """Scrape a specific portal for a company."""
    from app.database import SessionLocal
    from app.models import Company
    from app.services.audit import log_event

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError(f"Company {company_id} not found")

        if portal == "gst":
            from app.services.gst_scraper import GSTScraper
            scraper = GSTScraper(company)
        elif portal == "roc":
            from app.services.roc_scraper import ROCScraper
            scraper = ROCScraper(company)
        else:
            raise ValueError(f"Unknown portal: {portal}")

        try:
            result = scraper.run()
        finally:
            scraper.cleanup()

        log_event(
            db=db,
            company_id=company_id,
            event_type=f"scrape_{portal}_complete",
            details={"status": result["status"]},
        )

        return result

    except Exception as exc:
        logger.error(f"Portal scrape failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    finally:
        db.close()
