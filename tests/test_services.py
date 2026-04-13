"""Tests for Phase 1 services: scraper, extraction, classification, audit."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from app.services.classification import classify_document_text, find_flags, _rule_based_classify
from app.services.bank_scraper import BankStatementParser
from app.services.document_intake import intake_document, MAX_FILE_SIZE
from app.services.audit import log_event
from app.models import Company, Document, AuditLog


# --- Classification Tests ---

def test_find_flags_late_filing():
    text = "This filing is overdue. A penalty of INR 5000 has been imposed."
    flags = find_flags(text)
    assert "late_filing" in flags


def test_find_flags_missing_attachment():
    text = "Annexure B is pending. Please attach the missing document."
    flags = find_flags(text)
    assert "missing_attachment" in flags


def test_find_flags_reconciliation():
    text = "There is a discrepancy in the amounts. Reconciliation is needed."
    flags = find_flags(text)
    assert "reconciliation_needed" in flags


def test_find_flags_notice():
    text = "A show cause notice has been issued for non-compliance."
    flags = find_flags(text)
    assert "notice_received" in flags


def test_find_flags_clean_document():
    text = "GST return filed successfully. All invoices matched. No issues found."
    flags = find_flags(text)
    assert len(flags) == 0


def test_classify_compliant_document():
    text = "GSTR-1 filed on time. All sections complete. Filing confirmed by portal. Compliant status."
    result = classify_document_text(text)
    assert result["status"] == "compliant"
    assert result["confidence"] > 0
    assert isinstance(result["flags"], list)
    assert "model_version" in result


def test_classify_non_compliant_document():
    text = "NOTICE: Late filing penalty of INR 50000. Overdue by 30 days. Non-compliant. Show cause notice issued."
    result = classify_document_text(text)
    assert result["status"] == "non_compliant"
    assert "late_filing" in result["flags"]
    assert "notice_received" in result["flags"]


def test_classify_review_required():
    text = "Filing status unclear. Some discrepancy found. Reconciliation may be needed."
    result = classify_document_text(text)
    assert result["status"] in ("review_required", "non_compliant", "compliant")


def test_rule_based_classify_compliant():
    result = _rule_based_classify("Filed on time. Compliant. All good.", [], {})
    assert result["status"] == "compliant"
    assert result["method"] == "rule_based"


def test_rule_based_classify_non_compliant():
    result = _rule_based_classify(
        "Penalty notice. Non-compliant status.",
        ["late_filing", "notice_received"],
        {},
    )
    assert result["status"] == "non_compliant"


# --- Bank Statement Parser Tests ---

def test_bank_statement_extract_transactions():
    parser = BankStatementParser.__new__(BankStatementParser)
    text = """
    Opening Balance: 50,000.00
    01/03/2024 Salary Credit                          25,000.00 75,000.00
    05/03/2024 Rent Payment         15,000.00                   60,000.00
    10/03/2024 GST Payment          5,000.00                    55,000.00
    Closing Balance: 55,000.00
    Total Credits: 25,000.00
    Total Debits: 20,000.00
    """
    result = parser.parse_statement(text)
    assert result["portal"] == "bank"
    assert result["opening_balance"] == 50000.0
    assert result["closing_balance"] == 55000.0
    assert result["total_credits"] == 25000.0
    assert result["total_debits"] == 20000.0
    assert len(result["transactions"]) > 0


def test_bank_statement_empty_text():
    parser = BankStatementParser.__new__(BankStatementParser)
    result = parser.parse_statement("")
    assert result["transactions"] == []


# --- Document Intake Tests ---

def test_intake_rejects_oversized_file(test_db):
    large_content = b"x" * (MAX_FILE_SIZE + 1)
    with pytest.raises(ValueError, match="File too large"):
        intake_document(
            db=test_db,
            company_id=str(uuid4()),
            source="upload",
            document_type="gst_return",
            content=large_content,
        )


def test_intake_deduplicates(test_db):
    partner_id = uuid4()
    company = Company(id=uuid4(), partner_id=partner_id, name="Test Co", gst_id="27AABAA0000A1Z5")
    test_db.add(company)
    test_db.commit()

    content = b"test document content"
    doc1 = intake_document(
        db=test_db,
        company_id=str(company.id),
        source="upload",
        document_type="gst_return",
        content=content,
    )
    doc2 = intake_document(
        db=test_db,
        company_id=str(company.id),
        source="upload",
        document_type="gst_return",
        content=content,
    )
    assert doc1.id == doc2.id  # Same document returned


# --- Audit Log Tests ---

def test_audit_log_event(test_db):
    partner_id = uuid4()
    company = Company(id=uuid4(), partner_id=partner_id, name="Audit Co", gst_id="29BBBBB1111B2Z3")
    test_db.add(company)
    test_db.commit()

    log = log_event(
        db=test_db,
        company_id=str(company.id),
        event_type="test_event",
        details={"key": "value"},
    )
    assert log.event_type == "test_event"
    assert log.details == {"key": "value"}

    # Verify it's persisted
    retrieved = test_db.query(AuditLog).filter(AuditLog.id == log.id).first()
    assert retrieved is not None
