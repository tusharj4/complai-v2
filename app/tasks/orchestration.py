import hashlib
import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def test_task(self, message: str):
    logger.info(f"Test task executed: {message}")
    return {"status": "success", "message": message}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def scrape_and_classify_company(self, company_id: str):
    """
    Master orchestration job: scrape -> extract -> classify -> audit.
    Retries 3x with exponential backoff.
    """
    from app.database import SessionLocal
    from app.models import Company, Document
    from app.services.gst_scraper import GSTScraper
    from app.services.audit import log_event
    from app.tasks.workers import extract_and_classify

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError(f"Company {company_id} not found")

        logger.info(f"Starting scrape_and_classify for company {company_id}")

        # Step 1: Scrape GST portal
        scraper = GSTScraper(company)
        try:
            scrape_result = scraper.run()
        finally:
            scraper.cleanup()

        if scrape_result["status"] == "failed":
            raise Exception(f"Scraper failed: {scrape_result.get('error')}")

        # Log scraper success
        log_event(
            db=db,
            company_id=company_id,
            event_type="scraper_success",
            details={
                "scraper": "GST",
                "version": scrape_result.get("scraper_version", "1.0.0"),
                "data_points": len(scrape_result["data"].get("returns", [])),
            },
        )

        # Step 2: Create Document records for each return
        for return_data in scrape_result["data"].get("returns", []):
            content_hash = hashlib.sha256(str(return_data).encode()).hexdigest()

            existing = db.query(Document).filter(Document.content_hash == content_hash).first()
            if existing:
                continue

            doc = Document(
                company_id=company_id,
                source="scraper",
                document_type="gst_return",
                s3_path=f"gst/{company_id}/{return_data.get('filing_period', 'unknown')}.json",
                content_hash=content_hash,
                metadata_=return_data,
                extraction_status="extracted",  # Already structured data
            )
            db.add(doc)

        db.commit()

        # Step 3: Queue classification for extracted documents
        documents = (
            db.query(Document)
            .filter(Document.company_id == company_id, Document.extraction_status == "extracted")
            .all()
        )

        for doc in documents:
            extract_and_classify.apply_async(args=[str(doc.id)])

        logger.info(f"Queued {len(documents)} documents for classification")

        return {
            "company_id": company_id,
            "status": "success",
            "documents_queued": len(documents),
        }

    except Exception as exc:
        logger.error(f"scrape_and_classify failed: {exc}")
        try:
            log_event(
                db=db,
                company_id=company_id,
                event_type="scrape_and_classify_failed",
                details={"error": str(exc), "retry_count": self.request.retries},
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))

    finally:
        db.close()
