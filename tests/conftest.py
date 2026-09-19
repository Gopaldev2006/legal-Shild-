import os

# ── Must set DATABASE_URL BEFORE any app module is imported ──────────────────
# app/db/session.py reads settings.DATABASE_URL at import time.
# app/main.py calls Base.metadata.create_all(bind=engine) + init_db at import.
# By pointing at a file-based path we share ONE engine across all sessions.
# We use a named temp file so every test run starts fresh via setup_db fixture.
os.environ["DATABASE_URL"] = "sqlite:///./test_temp.db"

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
# This guarantees the db fixture, override_get_db, and app all share one DB.
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
