import hashlib
from uuid import UUID as PyUUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.auth import verify_token
from app.database import get_db
from app.models import Company, Document, Classification, AuditLog, WebhookEndpoint
from app.api.schemas import (
    CompanyCreate, CompanyResponse, DocumentCreate, DocumentResponse,
    ManualOverrideRequest, WebhookCreate, WebhookResponse,
)

router = APIRouter(prefix="/api/v1")


def _partner_uuid(current_user: dict) -> PyUUID:
    return PyUUID(current_user["partner_id"])


def _get_company_authorized(company_id: PyUUID, current_user: dict, db: Session) -> Company:
    """Helper to get a company and verify partner ownership."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.partner_id != _partner_uuid(current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return company


def _get_document_authorized(document_id: PyUUID, current_user: dict, db: Session) -> Document:
    """Helper to get a document and verify partner ownership."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    company = db.query(Company).filter(Company.id == doc.company_id).first()
    if company.partner_id != _partner_uuid(current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return doc


# ============================================================
# Company Routes
# ============================================================

@router.post("/companies", response_model=CompanyResponse)
async def create_company(
    req: CompanyCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    existing = db.query(Company).filter(Company.gst_id == req.gst_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company with this GST ID already exists")

    company = Company(
        partner_id=_partner_uuid(current_user),
        name=req.name,
        gst_id=req.gst_id,
        filing_deadlines=req.filing_deadlines,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/companies", response_model=list[CompanyResponse])
async def list_companies(
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    return (
        db.query(Company)
        .filter(Company.partner_id == _partner_uuid(current_user))
        .order_by(Company.created_at.desc())
        .all()
    )


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: PyUUID,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    return _get_company_authorized(company_id, current_user, db)


# ============================================================
# Scrape Trigger
# ============================================================

@router.post("/companies/{company_id}/scrape")
async def trigger_scrape(
    company_id: PyUUID,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    _get_company_authorized(company_id, current_user, db)
    from app.tasks.orchestration import scrape_and_classify_company
    job = scrape_and_classify_company.apply_async(args=[str(company_id)])
    return {"job_id": job.id, "status": "queued"}


# ============================================================
# Compliance Status
# ============================================================

@router.get("/companies/{company_id}/compliance-status")
async def get_compliance_status(
    company_id: PyUUID,
    request: Request,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    _get_company_authorized(company_id, current_user, db)

    # Redis cache check — 30 second TTL (matches portal auto-refresh interval)
    cache_key = f"compliance:{company_id}"
    cache_get = getattr(request.app.state, "cache_get", lambda k: None)
    cache_set = getattr(request.app.state, "cache_set", lambda k, v, ttl=30: None)

    cached = cache_get(cache_key)
    if cached:
        cached["_cached"] = True
        return cached

    documents = db.query(Document).filter(Document.company_id == company_id).all()

    docs_status = []
    for doc in documents:
        latest_class = (
            db.query(Classification)
            .filter(Classification.document_id == doc.id)
            .order_by(Classification.created_at.desc())
            .first()
        )
        docs_status.append({
            "document_id": str(doc.id),
            "document_type": doc.document_type,
            "extraction_status": doc.extraction_status,
            "status": latest_class.classification.get("status", "unknown") if latest_class else "pending",
            "confidence": latest_class.classification.get("confidence", 0) if latest_class else 0,
            "flags": latest_class.classification.get("flags", []) if latest_class else [],
            "last_checked": latest_class.created_at.isoformat() if latest_class else None,
        })

    overall_status = "compliant" if docs_status and all(
        d["status"] == "compliant" for d in docs_status
    ) else "at_risk" if docs_status else "no_data"

    result = {
        "company_id": str(company_id),
        "overall_status": overall_status,
        "documents": docs_status,
        "total_documents": len(docs_status),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "_cached": False,
    }

    # Store in cache (30s TTL)
    cache_set(cache_key, result, ttl=30)

    return result


# ============================================================
# Audit Log
# ============================================================

@router.get("/companies/{company_id}/audit-log")
async def get_audit_log(
    company_id: PyUUID,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    _get_company_authorized(company_id, current_user, db)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.company_id == company_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": str(log.id),
            "event_type": log.event_type,
            "details": log.details,
            "document_id": str(log.document_id) if log.document_id else None,
            "created_at": log.created_at.isoformat(),
            "created_by_user": str(log.created_by_user_id) if log.created_by_user_id else None,
        }
        for log in logs
    ]


# ============================================================
# Document Routes
# ============================================================

@router.post("/documents", response_model=DocumentResponse)
async def create_document(
    req: DocumentCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == req.company_id).first()
    if not company or company.partner_id != _partner_uuid(current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    content_hash = hashlib.sha256(f"{req.company_id}-{req.document_type}-{req.file_path}".encode()).hexdigest()

    doc = Document(
        company_id=req.company_id,
        source="upload",
        document_type=req.document_type,
        s3_path=req.file_path or "pending",
        content_hash=content_hash,
        metadata_=req.metadata,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: PyUUID,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    return _get_document_authorized(document_id, current_user, db)


# ============================================================
# Manual Override (Phase 2)
# ============================================================

@router.post("/documents/{document_id}/override")
async def override_classification(
    document_id: PyUUID,
    req: ManualOverrideRequest,
    request: Request,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    doc = _get_document_authorized(document_id, current_user, db)

    # Create new classification record with override
    classification = Classification(
        document_id=document_id,
        scraper_version="manual_override",
        model_version="manual_override",
        classification={
            "status": req.new_status,
            "confidence": 1.0,
            "flags": [],
            "method": "manual_override",
            "reason": req.reason,
            "overridden_by": current_user["user_id"],
        },
    )
    db.add(classification)

    # Update document status
    doc.extraction_status = "classified"
    db.commit()

    # Audit log
    from app.services.audit import log_event
    log_event(
        db=db,
        company_id=str(doc.company_id),
        event_type="manual_override",
        document_id=str(document_id),
        details={
            "new_status": req.new_status,
            "reason": req.reason,
            "overridden_by": current_user["user_id"],
        },
        user_id=current_user["user_id"],
    )

    # Invalidate compliance-status cache for this company
    cache_delete = getattr(request.app.state, "cache_delete", lambda k: None)
    cache_delete(f"compliance:{doc.company_id}")

    # Publish Kafka event
    from app.kafka_producer import publish_event, TOPIC_COMPLIANCE_UPDATES
    publish_event(TOPIC_COMPLIANCE_UPDATES, {
        "event_type": "manual_override",
        "company_id": str(doc.company_id),
        "document_id": str(document_id),
        "new_status": req.new_status,
    })

    return {"ok": True, "message": f"Classification overridden to {req.new_status}"}


# ============================================================
# Retry Document (Phase 2)
# ============================================================

@router.post("/documents/{document_id}/retry")
async def retry_document(
    document_id: PyUUID,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    doc = _get_document_authorized(document_id, current_user, db)

    # Reset status and re-queue
    doc.extraction_status = "pending"
    doc.error_details = None
    db.commit()

    from app.tasks.workers import extract_and_classify
    job = extract_and_classify.apply_async(args=[str(document_id)])

    # Audit log
    from app.services.audit import log_event
    log_event(
        db=db,
        company_id=str(doc.company_id),
        event_type="manual_retry",
        document_id=str(document_id),
        details={"triggered_by": current_user["user_id"]},
        user_id=current_user["user_id"],
    )

    return {"ok": True, "job_id": job.id, "message": "Retry queued"}


# ============================================================
# Webhook Endpoints (Task 4.1.3)
# ============================================================

@router.post("/webhooks", response_model=WebhookResponse)
async def create_webhook(
    req: WebhookCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Register a webhook endpoint to receive compliance events."""
    # If company_id provided, verify ownership
    if req.company_id:
        _get_company_authorized(req.company_id, current_user, db)

    webhook = WebhookEndpoint(
        partner_id=_partner_uuid(current_user),
        company_id=req.company_id,
        url=req.url,
        event_types=req.event_types,
        headers=req.headers or {},
        secret=req.secret,
        is_active=True,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    """List all webhook registrations for this partner."""
    return (
        db.query(WebhookEndpoint)
        .filter(WebhookEndpoint.partner_id == _partner_uuid(current_user))
        .order_by(WebhookEndpoint.created_at.desc())
        .all()
    )


@router.get("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: PyUUID,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    wh = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == webhook_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if wh.partner_id != _partner_uuid(current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return wh


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: PyUUID,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Deactivate a webhook (soft delete)."""
    wh = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == webhook_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if wh.partner_id != _partner_uuid(current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    wh.is_active = False
    db.commit()
    return {"ok": True, "message": "Webhook deactivated"}
