# CompLai v2 — API Documentation

Base URL: `https://api.complai.in` (production) | `http://localhost:8000` (local dev)

Interactive Swagger UI: `{base_url}/docs`

---

## Authentication

All `/api/v1/*` endpoints require a Bearer token.

### Get Token

```http
POST /token
Content-Type: application/json

{
  "partner_id": "partner-uuid-or-string",
  "user_id": "user-uuid-or-string"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Use the token in all subsequent requests:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Companies

### Create Company

```http
POST /api/v1/companies
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Acme Pvt Ltd",
  "gst_id": "27AABCU9603R1ZX",
  "filing_deadlines": {
    "gst_monthly": "20",
    "itr": "31-07"
  }
}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme Pvt Ltd",
  "gst_id": "27AABCU9603R1ZX",
  "filing_deadlines": {"gst_monthly": "20", "itr": "31-07"},
  "created_at": "2026-04-17T10:30:00Z"
}
```

**Errors:**
- `400 Bad Request` — Invalid GST ID format or duplicate GST ID
- `401 Unauthorized` — Missing/invalid token

**GST ID format:** `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`

---

### List Companies

```http
GET /api/v1/companies
Authorization: Bearer {token}
```

**Response (200):** Array of CompanyResponse (filtered to requesting partner's companies only)

---

### Get Company

```http
GET /api/v1/companies/{company_id}
Authorization: Bearer {token}
```

**Errors:** `404 Not Found`, `403 Forbidden`

---

### Trigger Scrape

Queues a Celery job to scrape GST + ROC portals and classify all documents.

```http
POST /api/v1/companies/{company_id}/scrape
Authorization: Bearer {token}
```

**Response (200):**
```json
{
  "job_id": "a1b2c3d4-e5f6-...",
  "status": "queued"
}
```

---

### Compliance Status

Returns aggregated compliance status for all documents under a company.
**Cached for 30 seconds** (Redis). Cache is invalidated on manual override.

```http
GET /api/v1/companies/{company_id}/compliance-status
Authorization: Bearer {token}
```

**Response (200):**
```json
{
  "company_id": "550e8400-...",
  "overall_status": "compliant",
  "documents": [
    {
      "document_id": "abc123...",
      "document_type": "gst_return",
      "extraction_status": "classified",
      "status": "compliant",
      "confidence": 0.91,
      "flags": [],
      "last_checked": "2026-04-17T10:00:00Z"
    }
  ],
  "total_documents": 5,
  "last_updated": "2026-04-17T10:30:00Z",
  "_cached": false
}
```

`overall_status` values: `compliant` | `at_risk` | `no_data`

---

### Audit Log

```http
GET /api/v1/companies/{company_id}/audit-log?limit=100&offset=0
Authorization: Bearer {token}
```

**Query params:**
- `limit` (int, max 500, default 100)
- `offset` (int, default 0)

**Response (200):** Array of audit log entries, newest first.

```json
[
  {
    "id": "...",
    "event_type": "manual_override",
    "details": {"new_status": "compliant", "reason": "Filed manually"},
    "document_id": "...",
    "created_at": "2026-04-17T10:00:00Z",
    "created_by_user": "..."
  }
]
```

**Event types:** `scraper_success`, `roc_scrape_success`, `manual_override`, `manual_retry`, `extraction_complete`, `classification_complete`, `scrape_and_classify_failed`

---

## Documents

### Create Document (Upload)

```http
POST /api/v1/documents
Authorization: Bearer {token}
Content-Type: application/json

{
  "company_id": "550e8400-...",
  "document_type": "gst_return",
  "file_path": "s3://complai-docs/acme/gst-may-2025.pdf",
  "metadata": {"period": "May 2025", "form": "GSTR-3B"}
}
```

`document_type` values: `gst_return` | `itr` | `mca_filing` | `bank_statement`

**Response (200):** DocumentResponse with `extraction_status: "pending"` (extraction queued automatically)

---

### Get Document

```http
GET /api/v1/documents/{document_id}
Authorization: Bearer {token}
```

---

### Manual Override

Override the ML classification for a document. Creates a new Classification record with `method: "manual_override"`.

```http
POST /api/v1/documents/{document_id}/override
Authorization: Bearer {token}
Content-Type: application/json

{
  "new_status": "compliant",
  "reason": "Filed via offline channel, confirmed with client"
}
```

`new_status` values: `compliant` | `non_compliant` | `review_required`

**Response (200):**
```json
{"ok": true, "message": "Classification overridden to compliant"}
```

**Side effects:**
- Creates new Classification record with `manual_override` flag
- Publishes Kafka event to `compliance_updates` topic
- Invalidates Redis cache for this company's compliance-status
- Writes audit log entry

---

### Retry Document

Re-queue extraction + classification for a failed document.

```http
POST /api/v1/documents/{document_id}/retry
Authorization: Bearer {token}
```

**Response (200):**
```json
{"ok": true, "job_id": "...", "message": "Retry queued"}
```

---

## Webhooks

### Register Webhook

```http
POST /api/v1/webhooks
Authorization: Bearer {token}
Content-Type: application/json

{
  "url": "https://your-server.com/complai-webhook",
  "event_types": ["compliance_check_complete", "manual_override"],
  "company_id": null,
  "secret": "your-hmac-secret",
  "headers": {"X-Custom-Header": "value"}
}
```

`event_types` valid values:
- `compliance_check_complete`
- `manual_override`
- `scrape_complete`
- `scrape_failed`
- `extraction_complete`
- `extraction_failed`
- `classification_complete`
- `*` (wildcard — all events)

Set `company_id: null` to receive events for all partner companies.

**Response (200):** WebhookResponse

---

### List Webhooks

```http
GET /api/v1/webhooks
Authorization: Bearer {token}
```

---

### Get Webhook

```http
GET /api/v1/webhooks/{webhook_id}
Authorization: Bearer {token}
```

---

### Delete Webhook (Soft)

Marks webhook as inactive (soft delete).

```http
DELETE /api/v1/webhooks/{webhook_id}
Authorization: Bearer {token}
```

**Response (200):** `{"ok": true, "message": "Webhook deactivated"}`

---

### Webhook Payload Format

```json
{
  "event_type": "manual_override",
  "company_id": "550e8400-...",
  "document_id": "abc123-...",
  "new_status": "compliant",
  "timestamp": "2026-04-17T10:30:00Z"
}
```

### Webhook Security (HMAC-SHA256)

When `secret` is set, CompLai signs requests:

```
X-CompLai-Signature: sha256=<hmac_hex>
```

Verify on your server:
```python
import hmac, hashlib

def verify_signature(payload: bytes, secret: str, signature_header: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)
```

---

## System

### Health Check

```http
GET /health
```

**Response (200 OK / 503 Degraded):**
```json
{
  "status": "ok",
  "version": "2.0.0",
  "service": "complai-api",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "celery": "ok"
  },
  "features": {
    "rate_limiting": true
  }
}
```

---

## Rate Limits

| Scope | Limit |
|-------|-------|
| Per partner (JWT) | 1000 requests/minute |
| Global fallback (IP) | 1000 requests/minute |

Exceeded limit returns `429 Too Many Requests`:
```json
{"error": "Rate limit exceeded", "retry_after": 60}
```

---

## Error Codes

| Status | Meaning |
|--------|---------|
| 400 | Validation error (invalid GST ID, bad enum value, etc.) |
| 401 | Missing or invalid Bearer token |
| 403 | Token valid but partner doesn't own the requested resource |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 422 | Pydantic schema validation error (see response body for details) |
| 503 | Service degraded (DB/Redis issues) |
