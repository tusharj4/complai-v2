# CompLai v2

**Production-grade compliance automation platform** for Indian CS firm partners managing 1–500 private companies.

Automates the full compliance cycle: portal scraping (GST, ROC/MCA, Bank Statements) → OCR extraction → ML classification (XGBoost) → audit logging → real-time partner portal.

---

## Architecture

```
Partner Portal (Next.js 15)
        │
        ▼
FastAPI REST API  ──→  PostgreSQL 14
        │              (companies, documents,
        │               classifications, audit_log,
        │               webhook_endpoints)
        │
        ├──→ Celery Workers (RabbitMQ broker, Redis backend)
        │       ├── scrape_and_classify_company (GST + ROC)
        │       ├── extract_and_classify (OCR → XGBoost)
        │       └── classify_document (ML / rule-based fallback)
        │
        ├──→ Kafka  ──→ Webhook Consumer
        │    (compliance_updates, audit_events, scraper_events)
        │
        └──→ Redis  (response cache, rate limiting)
```

**Key components:**
- **FastAPI** + Pydantic v2 — REST API with partner isolation
- **PostgreSQL** + SQLAlchemy 2 + Alembic — ORM + migrations
- **Celery** + RabbitMQ — Task queue with DLQ, retry, exponential backoff
- **Kafka** — Event streaming with graceful fallback to logging
- **XGBoost** + TF-IDF — ML compliance classification (rule-based fallback)
- **Selenium** — Headless browser scraping (GST, ROC/MCA portals)
- **Tesseract** + PyMuPDF — Dual-path OCR (native PDF + scanned)
- **slowapi** — Per-partner rate limiting (Redis-backed)
- **Next.js 15** — Partner portal (App Router, React Query, Tailwind)

---

## Quick Start

### With Docker Compose (recommended)

```bash
git clone https://github.com/tusharj4/complai-v2.git
cd complai-v2
cp .env.example .env         # Edit JWT_SECRET at minimum
docker compose up --build
docker compose exec app alembic upgrade head
```

Services available:
| Service | URL |
|---------|-----|
| FastAPI + Swagger | http://localhost:8000/docs |
| RabbitMQ UI | http://localhost:15672 |
| Portal | http://localhost:3000 (run separately) |

### Without Docker (local dev)

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Running the portal

```bash
cd complai-portal
npm install
npm run dev   # http://localhost:3000
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Performance tests only
pytest tests/test_performance.py -v

# Load test (Locust)
locust -f tests/load_test.py --host=http://localhost:8000
```

**Current status:** 44+ tests passing, 0 failures.

---

## API

Interactive docs: `http://localhost:8000/docs`  
Full documentation: [`docs/API.md`](docs/API.md)

Quick example:
```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"partner_id":"acme-cs","user_id":"tushar"}' | jq -r .access_token)

# Create a company
curl -X POST http://localhost:8000/api/v1/companies \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Pvt Ltd","gst_id":"27AABCU9603R1ZX"}'
```

---

## Project Structure

```
app/
  main.py              # FastAPI app + rate limiting + Redis cache helpers
  config.py            # Pydantic settings (env vars)
  database.py          # SQLAlchemy engine, SessionLocal
  auth.py              # JWT Bearer authentication
  celery_app.py        # Celery config, queues, task routing
  kafka_producer.py    # Kafka publisher with graceful fallback
  api/
    routes.py          # All API endpoints (companies, documents, webhooks)
    schemas.py         # Pydantic request/response models
  models/
    company.py         # Company ORM model
    document.py        # Document ORM model (gst_return, itr, mca_filing, bank_statement)
    classification.py  # Classification results
    audit_log.py       # Immutable audit trail
    extraction_cache.py# OCR result cache
    webhook.py         # Webhook endpoint registrations
    indexes.py         # Composite indexes for query optimization
  services/
    scraper.py         # BasePortalScraper ABC (retry, backoff, lazy browser)
    gst_scraper.py     # GST portal scraper (Selenium + BeautifulSoup)
    roc_scraper.py     # ROC/MCA portal scraper (full: filings, directors, charges)
    bank_scraper.py    # Bank statement parser (ICICI/HDFC/Axis/SBI/Kotak + generic)
    extraction.py      # PDF extraction (native + OCR path)
    classification.py  # XGBoost + TF-IDF + rule-based fallback
    document_intake.py # Document upload: validation, dedup, S3, queue
    audit.py           # Audit log service
    webhook_consumer.py# Kafka consumer → HTTP webhook dispatch (HMAC-signed)
  tasks/
    orchestration.py   # scrape_and_classify_company master task (GST + ROC)
    workers.py         # extract_and_classify, classify_document, scrape_portal
  utils/
    alerts.py          # Datadog + Slack alerting
  ml/
    train.py           # XGBoost training pipeline (synthetic data → F1 > 0.90)
complai-portal/        # Next.js 15 partner portal
  src/app/             # App Router pages
  src/components/      # Header, StatusBadge, CompanyCard, OverrideModal
  src/hooks/           # useAuth
  src/lib/api.ts       # Axios client + all API functions
docs/
  API.md               # API endpoint reference
  DEPLOYMENT.md        # Local + AWS production deployment guide
  TROUBLESHOOTING.md   # Common issues + alert runbooks
scripts/
  backup.sh            # pg_dump + gzip + optional S3 upload
  restore.sh           # Restore from backup
tests/
  conftest.py          # SQLite in-memory fixtures
  test_api.py          # API endpoint tests (18 tests)
  test_services.py     # Service unit tests (15 tests)
  test_performance.py  # Performance benchmarks
  load_test.py         # Locust load test
LAUNCH_CHECKLIST.md    # Go/no-go launch checklist
```

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 — Foundation | ✅ Complete | FastAPI skeleton, auth, DB models, Docker Compose, Celery |
| 1 — Core Pipeline | ✅ Complete | GST scraper, OCR, XGBoost classification, audit logging |
| 2 — Enhanced Pipeline | ✅ Complete | Kafka streaming, manual override, retry, monitoring |
| 3 — Partner Portal | ✅ Complete | Next.js portal with compliance dashboard |
| 4 — Scale & Polish | ✅ Complete | ROC/bank scrapers, webhooks, rate limiting, Redis caching, docs |

---

## Team

| Person | Role | Responsibilities |
|--------|------|-----------------|
| **Tushar** | CTO / Product Lead | API design, auth, classification, webhooks, docs |
| **Rohit** | CS Expert / Domain Lead | Compliance requirements, beta partner feedback |
| **Priya** | Senior Backend Engineer | Scrapers, OCR, ML pipeline, orchestration, load testing |
| **Arjun** | Full-Stack Engineer | DB, Kafka, portal, monitoring, DevOps |

---

## Contributing

1. Branch from `main`: `git checkout -b feat/your-feature`
2. Write tests for new functionality
3. Run `pytest tests/ -v` — all tests must pass
4. Run `npm run build` in `complai-portal/` — zero TypeScript errors
5. Open a PR with clear description of changes

**Code style:** black + isort (Python), ESLint (TypeScript)

---

## License

Private — CompLai v2 © 2026 CompLai Technologies
