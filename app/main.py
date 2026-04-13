import jwt as pyjwt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
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
async def health_check():
    return {
        "status": "ok",
        "version": "2.0.0",
        "service": "complai-api",
    }


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
