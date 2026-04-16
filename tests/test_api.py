"""Tests for API endpoints: health, auth, companies, documents, compliance, audit."""


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "CompLai" in response.json()["message"]


def test_get_token(client):
    response = client.post("/token", json={"partner_id": "test-partner", "user_id": "test-user"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_create_company(client, auth_headers):
    response = client.post(
        "/api/v1/companies",
        json={"name": "Acme Pvt Ltd", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Acme Pvt Ltd"
    assert data["gst_id"] == "27AABAA0000A1Z5"


def test_create_company_invalid_gst(client, auth_headers):
    response = client.post(
        "/api/v1/companies",
        json={"name": "Bad GST Co", "gst_id": "INVALID_GST_123"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_company_duplicate_gst(client, auth_headers):
    client.post(
        "/api/v1/companies",
        json={"name": "First Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    response = client.post(
        "/api/v1/companies",
        json={"name": "Second Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_list_companies(client, auth_headers):
    client.post(
        "/api/v1/companies",
        json={"name": "Co One", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/companies",
        json={"name": "Co Two", "gst_id": "29AABAA0000A1Z3"},
        headers=auth_headers,
    )
    response = client.get("/api/v1/companies", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_company(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Get Me Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]
    response = client.get(f"/api/v1/companies/{company_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Get Me Co"


def test_get_company_unauthorized(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Secret Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    import jwt as pyjwt
    from uuid import uuid4
    from app.config import settings

    other_token = pyjwt.encode(
        {"sub": str(uuid4()), "partner_id": str(uuid4())},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}
    response = client.get(f"/api/v1/companies/{company_id}", headers=other_headers)
    assert response.status_code == 403


def test_unauthenticated_request(client):
    response = client.get("/api/v1/companies")
    assert response.status_code == 403


# --- Compliance Status ---

def test_compliance_status_no_documents(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Empty Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/companies/{company_id}/compliance-status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "no_data"
    assert data["total_documents"] == 0


def test_compliance_status_with_documents(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Status Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    # Create a document
    client.post(
        "/api/v1/documents",
        json={"company_id": company_id, "document_type": "gst_return"},
        headers=auth_headers,
    )

    response = client.get(f"/api/v1/companies/{company_id}/compliance-status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_documents"] == 1
    assert data["documents"][0]["status"] == "pending"


# --- Audit Log ---

def test_audit_log_empty(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Audit Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/companies/{company_id}/audit-log", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


# --- Document CRUD ---

def test_create_document(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Doc Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    doc_resp = client.post(
        "/api/v1/documents",
        json={"company_id": company_id, "document_type": "gst_return", "metadata": {"period": "Q1"}},
        headers=auth_headers,
    )
    assert doc_resp.status_code == 200
    assert doc_resp.json()["document_type"] == "gst_return"
    assert doc_resp.json()["extraction_status"] == "pending"


# --- Manual Override (Phase 2) ---

def test_manual_override(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Override Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    doc_resp = client.post(
        "/api/v1/documents",
        json={"company_id": company_id, "document_type": "gst_return"},
        headers=auth_headers,
    )
    doc_id = doc_resp.json()["id"]

    override_resp = client.post(
        f"/api/v1/documents/{doc_id}/override",
        json={"new_status": "compliant", "reason": "Manually verified by auditor"},
        headers=auth_headers,
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["ok"] is True

    # Verify compliance status updated
    status_resp = client.get(f"/api/v1/companies/{company_id}/compliance-status", headers=auth_headers)
    assert status_resp.json()["documents"][0]["status"] == "compliant"
    assert status_resp.json()["overall_status"] == "compliant"


def test_manual_override_invalid_status(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Bad Override Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    doc_resp = client.post(
        "/api/v1/documents",
        json={"company_id": company_id, "document_type": "gst_return"},
        headers=auth_headers,
    )
    doc_id = doc_resp.json()["id"]

    override_resp = client.post(
        f"/api/v1/documents/{doc_id}/override",
        json={"new_status": "invalid_status", "reason": "Testing"},
        headers=auth_headers,
    )
    assert override_resp.status_code == 422


# --- Retry Endpoint (Phase 2) ---

def test_retry_document(client, auth_headers, monkeypatch):
    # Mock Celery task to avoid Redis dependency
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.id = "mock-job-id"
    monkeypatch.setattr("app.tasks.workers.extract_and_classify.apply_async", lambda **kwargs: mock_result)

    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Retry Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    doc_resp = client.post(
        "/api/v1/documents",
        json={"company_id": company_id, "document_type": "gst_return"},
        headers=auth_headers,
    )
    doc_id = doc_resp.json()["id"]

    retry_resp = client.post(f"/api/v1/documents/{doc_id}/retry", headers=auth_headers)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["ok"] is True

    # Verify status reset to pending
    doc_check = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert doc_check.json()["extraction_status"] == "pending"


# --- Audit Log with Override Events ---

def test_audit_log_records_override(client, auth_headers):
    create_resp = client.post(
        "/api/v1/companies",
        json={"name": "Audit Override Co", "gst_id": "27AABAA0000A1Z5"},
        headers=auth_headers,
    )
    company_id = create_resp.json()["id"]

    doc_resp = client.post(
        "/api/v1/documents",
        json={"company_id": company_id, "document_type": "gst_return"},
        headers=auth_headers,
    )
    doc_id = doc_resp.json()["id"]

    # Override
    client.post(
        f"/api/v1/documents/{doc_id}/override",
        json={"new_status": "non_compliant", "reason": "Found issues during review"},
        headers=auth_headers,
    )

    # Check audit log
    log_resp = client.get(f"/api/v1/companies/{company_id}/audit-log", headers=auth_headers)
    assert log_resp.status_code == 200
    logs = log_resp.json()
    assert any(log["event_type"] == "manual_override" for log in logs)
