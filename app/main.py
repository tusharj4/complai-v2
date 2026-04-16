"""
CompLai API — main application entry point.

Phase 4 additions:
- Rate limiting via slowapi (100 req/min per partner JWT, 1000/min per IP globally)
- Redis caching for high-traffic endpoints (/compliance-status)
- Webhook consumer startup (background thread)
"""

import json
import logging
import jwt as pyjwt

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.api.routes import router
from app.api.schemas import TokenRequest, TokenResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiting setup (slowapi — Redis-backed)
# ---------------------------------------------------------------------------
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    def _get_partner_id(request: Request) -> str:
        """Rate-limit key: partner_id from JWT (falls back to IP)."""
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                token = auth.split(" ", 1)[1]
                payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
                return f"partner:{payload.get('partner_id', get_remote_address(request))}"
            except Exception:
                pass
        return f"ip:{get_remote_address(request)}"

    limiter = Limiter(
        key_func=_get_partner_id,
        storage_uri=settings.REDIS_URL,
        default_limits=["1000/minute"],  # Global default
    )
    RATE_LIMITING_ENABLED = True
    logger.info("Rate limiting enabled (Redis-backed)")

except ImportError:
    limiter = None
    RATE_LIMITING_ENABLED = False
    logger.warning("slowapi not installed — rate limiting disabled. Run: pip install slowapi")

# ---------------------------------------------------------------------------
# Redis cache client (lazy)
# ---------------------------------------------------------------------------
_redis_client = None

def get_redis():
    """Get Redis client for caching (lazy init, fails gracefully)."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


def cache_get(key: str):
    """Get cached value. Returns None if cache miss or unavailable."""
    r = get_redis()
    if not r:
        return None
    try:
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def cache_set(key: str, value, ttl: int = 30):
    """Set cache value with TTL in seconds. Fails silently if Redis unavailable."""
    r = get_redis()
    if not r:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete(key: str):
    """Delete cache entry (used on write operations)."""
    r = get_redis()
    if not r:
        return
    try:
        r.delete(key)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("CompLai API starting up...")
    logger.info(f"Rate limiting: {'enabled' if RATE_LIMITING_ENABLED else 'disabled'}")
    if settings.JWT_SECRET in ("changeme-in-production", "secret"):
        logger.warning("⚠️  JWT_SECRET is using a default value — change before production!")
    yield
    # Shutdown
    logger.info("CompLai API shutting down...")


app = FastAPI(
    title="CompLai API",
    version="2.0.0",
    description="Compliance Automation Platform for CS Partners",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register rate limiting middleware
if RATE_LIMITING_ENABLED and limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

app.include_router(router)

# Expose cache helpers for use in routes
app.state.cache_get = cache_get
app.state.cache_set = cache_set
app.state.cache_delete = cache_delete




# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    health = {
        "status": "ok",
        "version": "2.0.0",
        "service": "complai-api",
        "checks": {},
        "features": {
            "rate_limiting": RATE_LIMITING_ENABLED,
        },
    }

    # Database
    try:
        db.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception:
        health["checks"]["database"] = "failed"
        health["status"] = "degraded"

    # Redis
    try:
        r = get_redis()
        if r:
            health["checks"]["redis"] = "ok"
        else:
            health["checks"]["redis"] = "unavailable"
    except Exception:
        health["checks"]["redis"] = "unavailable"

    # Celery
    try:
        from app.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=1)
        if insp.ping():
            health["checks"]["celery"] = "ok"
        else:
            health["checks"]["celery"] = "no_workers"
    except Exception:
        health["checks"]["celery"] = "unavailable"

    status_code = 200 if health["status"] == "ok" else 503
    return JSONResponse(content=health, status_code=status_code)


# ---------------------------------------------------------------------------
# Root + Token
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "CompLai API v2.0", "docs": "/docs"}


@app.post("/token", response_model=TokenResponse)
async def get_token(req: TokenRequest):
    payload = {"sub": req.user_id, "partner_id": req.partner_id}
    token = pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return TokenResponse(access_token=token)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
