import os

# ── Must set DATABASE_URL BEFORE any app module is imported ──────────────────
os.environ["DATABASE_URL"] = "sqlite:///./test_temp.db"
# Disable JTI revocation for old tests (they don't create UserSession rows)
os.environ["REVOCATION_ENABLED"] = "false"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models                   # registers all models on Base.metadata
from app.db import session as db_session   # import AFTER env var is set
from app.db.base import Base
from app.main import app             # triggers create_all + init_db
from app.api.deps import get_db

# ── Reuse the EXACT engine that app/db/session.py created ────────────────────
engine = db_session.engine
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Drop and recreate all tables before each test for isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Yield a clean database session per test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True, scope="session")
def disable_rate_limiting():
    """
    Disable SlowAPI rate limiting for the entire root test session.
    Old tests share a single IP and would otherwise hit the 5/min login limit.
    """
    from app.core.limiter import limiter
    from starlette.requests import Request

    original = limiter._check_request_limit

    def _noop(request: Request, endpoint, *args, **kwargs):
        request.state.view_rate_limit = None

    limiter._check_request_limit = _noop
    yield
    limiter._check_request_limit = original
