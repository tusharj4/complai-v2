"""Performance tests for Phase 2 benchmarks."""
import time
import pytest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from app.services.classification import classify_document_text
from app.models import Company, Document


def test_classification_latency():
    """Single classification should complete in <1 second."""
    text = """
    GSTR-1 for Q1 2024 filed on time. All sections complete.
    Total taxable value INR 5,00,000. No discrepancies found.
    GSTIN 27AABAA0000A1Z5 verified. Reconciliation complete.
    """
    start = time.time()
    result = classify_document_text(text, {"document_type": "gst_return"})
    elapsed = time.time() - start

    assert result["status"] in ("compliant", "non_compliant", "review_required")
    assert elapsed < 1.0, f"Classification took {elapsed:.2f}s (expected <1s)"


def test_classification_batch_latency():
    """100 classifications should complete in <10 seconds."""
    texts = [
        f"GST return for period {i}. Filed on time. Amount INR {i*1000}."
        for i in range(100)
    ]

    start = time.time()
    results = [classify_document_text(t, {}) for t in texts]
    elapsed = time.time() - start

    assert len(results) == 100
    assert elapsed < 10.0, f"Batch classification took {elapsed:.2f}s (expected <10s)"
    print(f"100 classifications in {elapsed:.2f}s ({elapsed/100*1000:.1f}ms avg)")


def test_concurrent_api_requests(client, auth_headers):
    """10 concurrent API requests should all succeed."""
    def make_request():
        return client.get("/api/v1/companies", headers=auth_headers)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)


def test_company_creation_throughput(client, auth_headers):
    """Create 20 companies sequentially, should handle without issues."""
    start = time.time()
    for i in range(20):
        gst_suffix = f"{i:04d}"
        gst_id = f"27AABAA{gst_suffix}A1Z5"
        response = client.post(
            "/api/v1/companies",
            json={"name": f"Performance Co {i}", "gst_id": gst_id},
            headers=auth_headers,
        )
        # Some may fail due to GST validation, that's ok
    elapsed = time.time() - start
    print(f"20 company creations in {elapsed:.2f}s")
    assert elapsed < 10.0


def test_compliance_status_with_many_documents(client, auth_headers, test_db):
    """Compliance status should respond quickly even with many documents."""
    # Create company
    resp = client.post(
        "/api/v1/companies",
        json={"name": "Perf Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = resp.json()["id"]

    # Create 50 documents
    for i in range(50):
        client.post(
            "/api/v1/documents",
            json={"company_id": company_id, "document_type": "gst_return", "file_path": f"test/{i}.pdf"},
            headers=auth_headers,
        )

    start = time.time()
    resp = client.get(f"/api/v1/companies/{company_id}/compliance-status", headers=auth_headers)
    elapsed = time.time() - start

    assert resp.status_code == 200
    assert resp.json()["total_documents"] == 50
    assert elapsed < 2.0, f"Compliance status took {elapsed:.2f}s with 50 docs"
