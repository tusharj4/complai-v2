# CompLai v2 — Deployment Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Docker | ≥ 24 | Docker Desktop or Engine |
| Docker Compose | ≥ 2.x | Bundled with Docker Desktop |
| Python | 3.11+ | For local dev without Docker |
| Node.js | 18+ | For portal development |
| PostgreSQL | 14+ | Provided via Docker in dev |

---

## Local Development (Docker Compose)

```bash
# 1. Clone the repo
git clone https://github.com/tusharj4/complai-v2.git
cd complai-v2

# 2. Copy and configure environment
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET to something strong

# 3. Start all services (PostgreSQL, Redis, RabbitMQ, Kafka, API, Workers)
docker compose up --build

# 4. Run migrations
docker compose exec app alembic upgrade head

# 5. Verify health
curl http://localhost:8000/health

# 6. Get an auth token for local testing
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"partner_id": "test-partner", "user_id": "test-user"}'
```

### Service ports (local)

| Service | URL | Credentials |
|---------|-----|-------------|
| FastAPI | http://localhost:8000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |
| PostgreSQL | localhost:5432 | complai / complai |
| Redis | localhost:6379 | — |
| RabbitMQ UI | http://localhost:15672 | guest / guest |
| Kafka | localhost:9092 | — |

---

## Production Deployment (AWS)

### Infrastructure overview

```
Internet → ALB → ECS Fargate (API) → RDS PostgreSQL
                                    → ElastiCache Redis
                                    → Amazon MQ (RabbitMQ)
                                    → MSK (Kafka)
                                    → S3 (document storage)
ECS Fargate (Celery worker)
ECS Fargate (Webhook consumer)
```

### Step-by-step

#### 1. Build and push Docker images

```bash
# Authenticate to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
  <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com

# Build
docker build -t complai-api:v2.0 .

# Tag and push
docker tag complai-api:v2.0 <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/complai-api:v2.0
docker push <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/complai-api:v2.0
```

#### 2. Set environment variables (AWS Secrets Manager or SSM)

```bash
# Store secrets
aws secretsmanager create-secret --name complai/prod/env \
  --secret-string file://.env.prod

# Required production env vars:
DATABASE_URL=postgresql://complai:<pass>@<rds-endpoint>:5432/complai
REDIS_URL=redis://<elasticache-endpoint>:6379
RABBITMQ_URL=amqp://complai:<pass>@<amazonmq-endpoint>:5671
JWT_SECRET=<cryptographically-random-64-char-string>
KAFKA_BOOTSTRAP_SERVERS=<msk-bootstrap>:9092
S3_BUCKET=complai-documents-prod
DATADOG_API_KEY=<your-datadog-key>
SLACK_WEBHOOK_URL=<your-slack-webhook>
```

#### 3. Run database migrations

```bash
# Via ECS exec or one-off task:
aws ecs run-task \
  --cluster complai-prod \
  --task-definition complai-migrate \
  --overrides '{"containerOverrides":[{"name":"app","command":["alembic","upgrade","head"]}]}'
```

#### 4. Deploy ECS services

```bash
# Update service with new image
aws ecs update-service \
  --cluster complai-prod \
  --service complai-api \
  --force-new-deployment

aws ecs update-service \
  --cluster complai-prod \
  --service complai-worker \
  --force-new-deployment
```

#### 5. Verify deployment

```bash
curl https://api.complai.in/health
# Expected: {"status": "ok", "checks": {"database": "ok", "redis": "ok", ...}}
```

---

## Portal Deployment (Vercel)

```bash
cd complai-portal

# Set environment variable
vercel env add NEXT_PUBLIC_API_URL production
# Enter: https://api.complai.in

# Deploy
vercel --prod
```

### Portal environment variables

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://api.complai.in` |

---

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "add_webhook_endpoints_table"

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Check current revision
alembic current

# View history
alembic history
```

---

## Backup & Restore

```bash
# Manual backup
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh /path/to/backup.sql.gz
```

Automated backups run daily at 2 AM via `celery beat` (see `celery_app.py`).

---

## Scaling

### Horizontal scaling

- **API**: Stateless — scale ECS desired count up. All session state in DB/Redis.
- **Celery workers**: Add more `celery_worker` tasks. They pull from the same RabbitMQ queues.
- **Webhook consumer**: Single consumer per Kafka consumer group is sufficient for current load. Add replicas for failover.

### Vertical scaling

| Service | Starter | Production |
|---------|---------|-----------|
| API | 0.5 vCPU / 1GB | 2 vCPU / 4GB |
| Worker | 1 vCPU / 2GB | 4 vCPU / 8GB |
| PostgreSQL | db.t3.micro | db.r6g.large |
| Redis | cache.t3.micro | cache.r6g.large |

---

## Smoke Tests (post-deploy)

```bash
BASE=https://api.complai.in

# 1. Health check
curl $BASE/health

# 2. Get token
TOKEN=$(curl -s -X POST $BASE/token \
  -H "Content-Type: application/json" \
  -d '{"partner_id":"smoke-test","user_id":"smoke-user"}' | jq -r .access_token)

# 3. Create company
curl -s -X POST $BASE/api/v1/companies \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Test Co","gst_id":"27AABCU9603R1ZX"}'

# 4. List companies
curl -s $BASE/api/v1/companies -H "Authorization: Bearer $TOKEN"
```
