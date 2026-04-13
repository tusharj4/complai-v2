# CompLai v2

Compliance automation platform for Indian CS firm partners managing private companies. Automates compliance tracking through scraping, OCR, ML classification, and audit logging.

## Architecture

- **FastAPI** - REST API layer
- **PostgreSQL** - Primary database
- **Celery** + **RabbitMQ** - Task queue & orchestration
- **Redis** - Caching & Celery result backend
- **XGBoost** - Compliance classification (Phase 1)

## Quick Start

```bash
# Clone & setup
git clone <repo-url>
cd complai-v2
cp .env.example .env

# With Docker (recommended)
docker-compose up

# Without Docker (local dev)
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

## Running Tests

```bash
pytest tests/ -v --cov=app
```

## API Docs

Start the server and visit: http://localhost:8000/docs

## Project Structure

```
app/
  main.py          # FastAPI app entry point
  config.py        # Pydantic settings
  database.py      # SQLAlchemy setup
  auth.py          # JWT authentication
  celery_app.py    # Celery configuration
  api/             # Routes & schemas
  models/          # SQLAlchemy ORM models
  services/        # Business logic (scraper, OCR, classification)
  tasks/           # Celery tasks
  utils/           # Logging, errors, validators
tests/             # Pytest test suite
alembic/           # Database migrations
```

## Team

- **Tushar** - CTO/Product Lead
- **Rohit** - CS Expert/Domain Lead
- **Priya** - Senior Backend Engineer
- **Arjun** - Full-Stack Engineer
