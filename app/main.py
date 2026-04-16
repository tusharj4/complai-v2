import jwt as pyjwt
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.api.routes import router
from app.api.schemas import TokenRequest, TokenResponse

app = FastAPI(title="CompLai API", version="2.0.0", description="Compliance Automation Platform for CS Partners")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    health = {
        "status": "ok",
        "version": "2.0.0",
        "service": "complai-api",
        "checks": {},
    }

    # Check database
    try:
        db.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception:
        health["checks"]["database"] = "failed"
        health["status"] = "degraded"

    # Check Redis
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        health["checks"]["redis"] = "ok"
    except Exception:
        health["checks"]["redis"] = "unavailable"

    # Check RabbitMQ / Celery
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


@app.get("/")
async def root():
    return {"message": "CompLai API v2.0"}


@app.post("/token", response_model=TokenResponse)
async def get_token(req: TokenRequest):
    payload = {"sub": req.user_id, "partner_id": req.partner_id}
    token = pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return TokenResponse(access_token=token)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
