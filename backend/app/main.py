from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.limiter import limiter
from app.api.router import api_router
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.db.init_db import init_db
import app.models  # Ensure models are imported for metadata creation

# Initialize database tables & seed demo accounts
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    init_db(db)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend service for Secure AI Assistant for Legal Data Analysis.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── Rate limiter ──────────────────────────────────────────────────────────────
# Attach the SlowAPI limiter state and register the 429 exception handler.
# The limiter itself is a no-op when RATE_LIMIT_ENABLED=false in .env.
app.state.limiter = limiter

# Custom 429 handler — clean user-facing message + Retry-After header
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Return a clean, safe 429 response.
    Includes Retry-After so clients know when to retry.
    Does NOT expose internal limit details in the body.
    """
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Please try again later."},
        headers={"Retry-After": str(retry_after)},
    )

app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": "/docs",
        "health_check": f"{settings.API_V1_STR}/health"
    }
