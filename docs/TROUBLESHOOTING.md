# CompLai v2 — Troubleshooting Guide

## Common Issues & Fixes

---

### 1. Health check returns `"database": "failed"`

**Symptoms:** `GET /health` returns `{"status": "degraded", "checks": {"database": "failed"}}`

**Causes & Fixes:**

```bash
# Check PostgreSQL container
docker compose ps postgres
docker compose logs postgres --tail=50

# Verify connection string
echo $DATABASE_URL
# Should be: postgresql://complai:complai@postgres:5432/complai

# Test connection directly
docker compose exec postgres psql -U complai -d complai -c "SELECT 1;"

# If PostgreSQL is up but app can't connect — check network
docker compose exec app ping postgres
```

---

### 2. Celery tasks not executing

**Symptoms:** Documents stuck in `extraction_status = "pending"`. Tasks queued but never processed.

**Diagnosis:**

```bash
# Check worker status
docker compose logs celery_worker --tail=50

# Check RabbitMQ queue depths
docker compose exec rabbitmq rabbitmqctl list_queues

# Inspect active tasks
docker compose exec app celery -A app.celery_app inspect active

# Check for failed tasks in DLQ
docker compose exec app celery -A app.celery_app inspect reserved
```

**Fixes:**

```bash
# Restart worker
docker compose restart celery_worker

# Purge a stuck queue (caution — drops all queued tasks)
docker compose exec app celery -A app.celery_app purge -Q dlq
```

---

### 3. Kafka events not being published

**Symptoms:** Audit log missing events. Webhook consumer not receiving events.

```bash
# Check Kafka container
docker compose logs kafka --tail=50

# Verify topics exist
docker compose exec kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 --list

# Check producer logs
docker compose logs app | grep -i kafka

# Test publish manually
docker compose exec kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic compliance_updates
```

**Note:** The system falls back gracefully — if Kafka is unavailable, events are logged locally but not streamed. Webhooks will not fire during Kafka downtime.

---

### 4. OCR extraction failing

**Symptoms:** Documents stuck at `extraction_status = "failed"`. Logs show Tesseract errors.

```bash
# Check Tesseract installation
docker compose exec app which tesseract
docker compose exec app tesseract --version

# Check pdf2image dependencies (poppler)
docker compose exec app which pdftoppm

# Test extraction manually
docker compose exec app python -c "
from app.services.extraction import extract_document
# Will fail gracefully with an error message
"
```

**Fix for Docker:** Add to Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y tesseract-ocr poppler-utils
```

---

### 5. JWT authentication returning 401

**Symptoms:** API calls return `{"detail": "Invalid token"}` even with valid credentials.

**Diagnosis:**

```bash
# Verify JWT_SECRET matches between token generation and verification
echo $JWT_SECRET

# Decode a token manually
python3 -c "
import jwt
token = 'YOUR_TOKEN_HERE'
print(jwt.decode(token, options={'verify_signature': False}))
"

# Check token expiry — CompLai tokens don't expire by default in dev.
# If you've added expiry, verify clock sync.
```

---

### 6. Rate limiting returning 429 unexpectedly

**Symptoms:** API returns `429 Too Many Requests` for legitimate traffic.

```bash
# Check Redis connectivity (rate limit store)
docker compose exec app redis-cli -u $REDIS_URL ping

# Check current rate limit state for a partner
docker compose exec app redis-cli -u $REDIS_URL keys "LIMITER/*"

# Clear rate limit for a specific partner (emergency)
docker compose exec app redis-cli -u $REDIS_URL del "LIMITER/partner:PARTNER_ID_HERE"
```

Current limits:
- **Per partner**: 1000 requests/minute
- **Global default**: 1000 requests/minute

To raise limits, edit `app/main.py`:
```python
limiter = Limiter(key_func=_get_partner_id, default_limits=["5000/minute"])
```

---

### 7. Webhook deliveries failing

**Symptoms:** Webhooks registered but events not arriving at partner URL.

**Diagnosis:**

```bash
# Check webhook consumer process
docker compose logs webhook_consumer --tail=50

# Check last delivery status via API
curl $BASE/api/v1/webhooks -H "Authorization: Bearer $TOKEN"
# Look at "last_delivery_status" and "last_delivery_at"

# Verify Kafka is producing events
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic compliance_updates \
  --from-beginning --max-messages 5
```

**Common causes:**
- Webhook URL is unreachable from the server (firewall, VPN)
- Partner URL returning 5xx — consumer will retry 3x with backoff
- Wrong event_types filter — check `event_types` array in webhook config

---

### 8. Portal shows blank/loading state

**Symptoms:** Next.js portal loads but shows infinite loading or empty data.

```bash
# Check API URL in portal
cat complai-portal/.env.local
# NEXT_PUBLIC_API_URL should point to running API

# Check browser console for CORS errors
# If you see CORS errors, verify app/main.py has correct allow_origins

# Verify API is reachable from portal
curl http://localhost:8000/health
```

---

### 9. Database migration conflicts

**Symptoms:** `alembic upgrade head` fails with "Can't locate revision" or conflict error.

```bash
# Check current state
alembic current
alembic history

# If branches exist, merge them
alembic merge heads -m "merge_branches"
alembic upgrade head

# Nuclear option (dev only) — recreate DB
docker compose exec postgres psql -U complai -c "DROP DATABASE complai; CREATE DATABASE complai;"
alembic upgrade head
```

---

## Alerting Runbooks

### Alert: Scraper success rate < 90%

1. Check portal website status (MCA/GST portals often have maintenance windows)
2. Check Chrome/Selenium version compatibility: `docker compose exec app chromedriver --version`
3. Check IP-based blocking — portals may block datacenter IPs. Consider residential proxy.
4. Review scraper logs: `docker compose logs celery_worker | grep -i scraper`

### Alert: Classification latency > 5s

1. Check ML model loaded: `docker compose exec app python -c "from app.services.classification import _load_model; print(_load_model())"`
2. If model not loaded, rule-based fallback is active — latency increase is expected
3. Retrain model if F1 dropped: `docker compose exec app python app/ml/train.py`

### Alert: Error rate > 5%

1. Check API error logs: `docker compose logs app | grep -i error`
2. Look for DB connection pool exhaustion: increase `pool_size` in `database.py`
3. Check if Celery workers are overloaded: `celery inspect active`

### Alert: Queue depth > 1000

1. Scale up Celery workers: increase `--concurrency` in `docker-compose.yml`
2. Check for tasks stuck in retry loop: `celery inspect reserved`
3. If DLQ is growing, investigate root cause before purging

---

## Useful Commands

```bash
# View all running tasks
docker compose exec app celery -A app.celery_app inspect active

# Force-retry a specific document
curl -X POST $BASE/api/v1/documents/{doc_id}/retry \
  -H "Authorization: Bearer $TOKEN"

# Train ML model
docker compose exec app python app/ml/train.py

# Run test suite
pytest tests/ -v --tb=short

# Run load test (Locust)
cd complai-v2
locust -f tests/load_test.py --host=http://localhost:8000

# Backup database
./scripts/backup.sh

# Check Alembic migration status
docker compose exec app alembic current
```
