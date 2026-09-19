"""
conftest.py for backend/tests/
================================
Provides pytest fixtures for tests run from inside the backend/ directory:
    cd backend
    python -m pytest tests/ -v

Uses an isolated in-memory SQLite database so existing data is never touched.
"""

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # imports ALL models so Base.metadata is populated
from app.db.base import Base
from app.api.deps import get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
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
    Disable SlowAPI rate limiting for the entire test session.

    Patches _check_request_limit to be a no-op AND sets the
    view_rate_limit state attribute that slowapi's sync_wrapper reads.
    This prevents both rate-limit 429s and the 'State has no attribute
    view_rate_limit' AttributeError that occurs when the check is skipped.
    """
    from app.core.limiter import limiter
    from starlette.requests import Request

    original = limiter._check_request_limit

    def _noop(request: Request, endpoint, *args, **kwargs):
        # Set the attribute that sync_wrapper reads after the check
        request.state.view_rate_limit = None

    limiter._check_request_limit = _noop
    yield
    limiter._check_request_limit = original
