"""
Composite database indexes for query optimization.
Import this module to register indexes with SQLAlchemy.
"""

from sqlalchemy import Index
from app.models.company import Company
from app.models.document import Document
from app.models.classification import Classification
from app.models.audit_log import AuditLog

# Company: frequently query by partner + sort by created_at
idx_company_partner_created = Index(
    "idx_company_partner_created",
    Company.partner_id,
    Company.created_at,
)

# Document: frequently filter by company + status
idx_document_company_status = Index(
    "idx_document_company_status",
    Document.company_id,
    Document.extraction_status,
)

# Classification: lookup latest per document
idx_classification_document_created = Index(
    "idx_classification_document_created",
    Classification.document_id,
    Classification.created_at.desc(),
)

# AuditLog: paginated queries by company + time
idx_audit_company_created = Index(
    "idx_audit_company_created",
    AuditLog.company_id,
    AuditLog.created_at.desc(),
)
