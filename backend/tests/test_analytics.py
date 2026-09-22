"""
test_analytics.py — Admin Analytics API Tests
==============================================
Tests for:
  TC-01  Summary endpoint requires admin (reject public)
  TC-02  Summary endpoint requires admin (reject professional)
  TC-03  Unauthenticated request rejected
  TC-04  Admin can access summary endpoint
  TC-05  Summary response structure is correct
  TC-06  Recent activity requires admin
  TC-07  Admin can access recent activity
  TC-08  Recent activity response structure
  TC-09  User counts are accurate
  TC-10  Analytics service: Gemini count uses model_used='gemini'
  TC-11  Analytics service: fallback count uses model_used='free-legal-engine'
  TC-12  Analytics service: document count is accurate
  TC-13  Analytics failure is safe (no crash, no stack trace exposed)

Run:
    cd backend
    python -m pytest tests/test_analytics.py -v
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def tokens(client):
    def _login(email, password):
        r = client.post("/api/v1/auth/login",
                        json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed for {email}: {r.text}"
        return r.json()["access_token"]
    return {
        "public": _login("public@example.com",  "public123"),
        "pro":    _login("advocate@example.com", "advocate123"),
        "admin":  _login("admin@example.com",    "admin123"),
    }


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# TC-01 / TC-02 / TC-03  Authorization checks — summary
# ─────────────────────────────────────────────────────────────────────────────

class TestSummaryAuthorization:
    def test_public_user_denied_summary(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403, \
            f"PUBLIC_USER must be denied analytics summary, got {r.status_code}"

    def test_professional_denied_summary(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 403, \
            f"LEGAL_PROFESSIONAL must be denied analytics summary, got {r.status_code}"

    def test_unauthenticated_denied_summary(self, client):
        r = client.get("/api/v1/admin/analytics/summary")
        assert r.status_code in (401, 403), \
            f"Unauthenticated must be denied, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-04 / TC-05  Admin access + response structure
# ─────────────────────────────────────────────────────────────────────────────

class TestSummaryContent:
    def test_admin_can_access_summary(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200, \
            f"ADMIN must be allowed analytics summary, got {r.status_code}: {r.text}"

    def test_summary_has_required_top_level_keys(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200
        body = r.json()
        for key in ("users", "documents", "ai", "sessions", "generated_at"):
            assert key in body, f"Missing top-level key '{key}' in analytics summary"

    def test_users_section_has_required_fields(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["admin"]))
        users = r.json()["users"]
        for field in ("total", "public", "professionals", "admins",
                      "new_last_7_days", "new_last_30_days"):
            assert field in users, f"Missing field '{field}' in users section"
            assert isinstance(users[field], int), \
                f"Field '{field}' must be int, got {type(users[field])}"

    def test_documents_section_has_required_fields(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["admin"]))
        docs = r.json()["documents"]
        for field in ("total", "ready", "failed", "by_status", "by_type"):
            assert field in docs, f"Missing field '{field}' in documents section"

    def test_ai_section_has_required_fields(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["admin"]))
        ai = r.json()["ai"]
        for field in ("total_ai_responses", "total_rag_queries",
                      "gemini_queries", "fallback_queries", "gemini_percentage",
                      "total_conversations", "conversations_by_mode"):
            assert field in ai, f"Missing field '{field}' in ai section"

    def test_user_total_is_non_negative(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["admin"]))
        assert r.json()["users"]["total"] >= 0

    def test_summary_contains_no_sensitive_fields(self, client, tokens):
        """Ensure passwords, tokens, keys are absent from the entire response."""
        r = client.get("/api/v1/admin/analytics/summary",
                       headers=_auth(tokens["admin"]))
        body_str = r.text.lower()
        for forbidden in ("password", "jwt", "api_key", "gemini_api_key",
                          "encryption_key", "secret"):
            assert forbidden not in body_str, \
                f"Sensitive field '{forbidden}' found in analytics summary response"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06 / TC-07 / TC-08  Recent activity
# ─────────────────────────────────────────────────────────────────────────────

class TestRecentActivity:
    def test_public_user_denied_recent_activity(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/recent-activity",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_admin_can_access_recent_activity(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/recent-activity",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200, \
            f"ADMIN must be allowed recent activity, got {r.status_code}"

    def test_recent_activity_response_structure(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/recent-activity",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)

    def test_recent_activity_items_have_safe_fields(self, client, tokens):
        """Each item must have the expected fields and no sensitive content."""
        r = client.get("/api/v1/admin/analytics/recent-activity",
                       headers=_auth(tokens["admin"]))
        items = r.json()["items"]
        if items:
            item = items[0]
            for field in ("id", "event_type", "success", "created_at"):
                assert field in item, f"Missing field '{field}' in activity item"
            # Sensitive fields must NOT be present
            for forbidden in ("password", "token", "api_key", "content"):
                assert forbidden not in item, \
                    f"Sensitive field '{forbidden}' found in activity item"

    def test_recent_activity_limit_param(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/recent-activity?limit=5",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 5


# ─────────────────────────────────────────────────────────────────────────────
# TC-09 — TC-12  Analytics service unit tests (in-memory DB)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def in_memory_db():
    """Isolated in-memory SQLite DB with known seed data for unit tests."""
    from app.db.base import Base
    import app.models  # noqa: F401 — ensures all models registered

    engine  = create_engine("sqlite:///:memory:",
                             connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db      = Session()

    # Seed users
    from app.models.user import User, UserRole, VerificationStatus
    from app.core.security import get_password_hash

    users = [
        User(name="Alice", email="alice@t.com",
             password_hash=get_password_hash("x"),
             role=UserRole.PUBLIC_USER,
             verification_status=VerificationStatus.NOT_REQUIRED),
        User(name="Bob", email="bob@t.com",
             password_hash=get_password_hash("x"),
             role=UserRole.PUBLIC_USER,
             verification_status=VerificationStatus.NOT_REQUIRED),
        User(name="Carol", email="carol@t.com",
             password_hash=get_password_hash("x"),
             role=UserRole.LEGAL_PROFESSIONAL,
             verification_status=VerificationStatus.VERIFIED),
        User(name="Admin", email="admin@t.com",
             password_hash=get_password_hash("x"),
             role=UserRole.ADMIN,
             verification_status=VerificationStatus.VERIFIED),
    ]
    db.add_all(users)
    db.commit()
    for u in users:
        db.refresh(u)

    # Seed documents
    from app.models.document import LegalDocument, DocumentType, ProcessingStatus
    docs = [
        LegalDocument(owner_id=users[2].id, filename="a.pdf",
                      stored_filename="a.pdf", stored_path="/tmp/a.pdf",
                      file_type="pdf", file_size=1024, file_hash="h1",
                      document_type=DocumentType.CONTRACT,
                      processing_status=ProcessingStatus.READY),
        LegalDocument(owner_id=users[2].id, filename="b.pdf",
                      stored_filename="b.pdf", stored_path="/tmp/b.pdf",
                      file_type="pdf", file_size=2048, file_hash="h2",
                      document_type=DocumentType.STATUTE,
                      processing_status=ProcessingStatus.FAILED),
    ]
    db.add_all(docs)
    db.commit()

    # Seed conversations + chat messages
    from app.models.conversation import (
        Conversation, ChatMessage, ConversationMode, MessageRole
    )
    conv = Conversation(owner_id=users[2].id, title="Test conv",
                        mode=ConversationMode.GENERAL)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    messages = [
        ChatMessage(conversation_id=conv.id, role=MessageRole.USER,
                    content="Question 1"),
        ChatMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT,
                    content="Answer 1", model_used="gemini"),
        ChatMessage(conversation_id=conv.id, role=MessageRole.USER,
                    content="Question 2"),
        ChatMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT,
                    content="Answer 2", model_used="free-legal-engine"),
        ChatMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT,
                    content="Answer 3", model_used="gemini"),
    ]
    db.add_all(messages)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


class TestAnalyticsServiceUnit:

    def test_user_counts_are_accurate(self, in_memory_db):
        from app.services.analytics.analytics_service import _user_stats
        stats = _user_stats(in_memory_db)
        assert stats["total"]         == 4
        assert stats["public"]        == 2
        assert stats["professionals"] == 1
        assert stats["admins"]        == 1

    def test_document_counts_are_accurate(self, in_memory_db):
        from app.services.analytics.analytics_service import _document_stats
        stats = _document_stats(in_memory_db)
        assert stats["total"]  == 2
        assert stats["ready"]  == 1
        assert stats["failed"] == 1

    def test_gemini_count_uses_model_used_field(self, in_memory_db):
        from app.services.analytics.analytics_service import _ai_stats
        stats = _ai_stats(in_memory_db)
        assert stats["gemini_queries"]   == 2, \
            f"Expected 2 Gemini messages, got {stats['gemini_queries']}"
        assert stats["fallback_queries"] == 1, \
            f"Expected 1 fallback message, got {stats['fallback_queries']}"

    def test_total_ai_responses_correct(self, in_memory_db):
        from app.services.analytics.analytics_service import _ai_stats
        stats = _ai_stats(in_memory_db)
        # 3 assistant messages total
        assert stats["total_ai_responses"] == 3

    def test_gemini_percentage_calculation(self, in_memory_db):
        from app.services.analytics.analytics_service import _ai_stats
        stats = _ai_stats(in_memory_db)
        # 2 gemini out of 3 total = 66.7%
        assert 65.0 <= stats["gemini_percentage"] <= 67.0

    def test_summary_function_returns_all_sections(self, in_memory_db):
        from app.services.analytics.analytics_service import get_analytics_summary
        result = get_analytics_summary(in_memory_db)
        for key in ("users", "documents", "ai", "sessions", "generated_at"):
            assert key in result

    def test_analytics_service_handles_empty_db_gracefully(self):
        """Service must not crash or raise on an empty database."""
        from app.db.base import Base
        import app.models  # noqa: F401
        from app.services.analytics.analytics_service import get_analytics_summary

        engine = create_engine("sqlite:///:memory:",
                                connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        try:
            result = get_analytics_summary(db)
            assert result["users"]["total"] == 0
            assert result["documents"]["total"] == 0
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)


# ─────────────────────────────────────────────────────────────────────────────
# Timeseries endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTimeseriesAuthorization:
    def test_public_user_denied_timeseries(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_professional_denied_timeseries(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 403

    def test_unauthenticated_denied_timeseries(self, client):
        r = client.get("/api/v1/admin/analytics/timeseries")
        assert r.status_code in (401, 403)

    def test_admin_can_access_timeseries(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200


class TestTimeseriesStructure:
    def test_default_7_days_returns_7_entries(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries?days=7",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200
        body = r.json()
        assert body["days"] == 7
        assert len(body["data"]) == 7

    def test_1_day_returns_1_entry(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries?days=1",
                       headers=_auth(tokens["admin"]))
        body = r.json()
        assert body["days"] == 1
        assert len(body["data"]) == 1

    def test_30_days_returns_30_entries(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries?days=30",
                       headers=_auth(tokens["admin"]))
        body = r.json()
        assert body["days"] == 30
        assert len(body["data"]) == 30

    def test_each_entry_has_required_fields(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries?days=7",
                       headers=_auth(tokens["admin"]))
        entries = r.json()["data"]
        for entry in entries:
            for field in ("date", "users", "documents", "ai_total", "gemini", "fallback"):
                assert field in entry, f"Missing field '{field}' in timeseries entry"
            # All counts must be non-negative integers
            for field in ("users", "documents", "ai_total", "gemini", "fallback"):
                assert isinstance(entry[field], int), f"'{field}' must be int"
                assert entry[field] >= 0, f"'{field}' must be >= 0"

    def test_dates_are_in_ascending_order(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries?days=7",
                       headers=_auth(tokens["admin"]))
        dates = [e["date"] for e in r.json()["data"]]
        assert dates == sorted(dates), "Timeseries dates must be in ascending order"

    def test_dates_are_valid_iso_format(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries?days=7",
                       headers=_auth(tokens["admin"]))
        from datetime import datetime as dt
        for entry in r.json()["data"]:
            try:
                dt.strptime(entry["date"], "%Y-%m-%d")
            except ValueError:
                pytest.fail(f"Date '{entry['date']}' is not in YYYY-MM-DD format")

    def test_today_is_last_entry(self, client, tokens):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = client.get("/api/v1/admin/analytics/timeseries?days=7",
                       headers=_auth(tokens["admin"]))
        last_date = r.json()["data"][-1]["date"]
        assert last_date == today, f"Last entry must be today ({today}), got {last_date}"

    def test_gemini_plus_fallback_lte_ai_total(self, client, tokens):
        """gemini + fallback can be <= ai_total (error-fallback messages aren't counted)."""
        r = client.get("/api/v1/admin/analytics/timeseries?days=7",
                       headers=_auth(tokens["admin"]))
        for entry in r.json()["data"]:
            assert entry["gemini"] + entry["fallback"] <= entry["ai_total"], \
                f"gemini+fallback must be <= ai_total on {entry['date']}"

    def test_invalid_days_param_rejected(self, client, tokens):
        """days=0 or days=31 must be rejected."""
        for bad_days in (0, 31, 100):
            r = client.get(f"/api/v1/admin/analytics/timeseries?days={bad_days}",
                           headers=_auth(tokens["admin"]))
            assert r.status_code == 422, \
                f"days={bad_days} must be rejected with 422, got {r.status_code}"

    def test_response_has_generated_at(self, client, tokens):
        r = client.get("/api/v1/admin/analytics/timeseries?days=7",
                       headers=_auth(tokens["admin"]))
        assert "generated_at" in r.json()


class TestTimeseriesServiceUnit:
    """Unit tests against the in-memory DB with known seed data."""

    def test_timeseries_7_days_returns_7_items(self, in_memory_db):
        from app.services.analytics.analytics_service import get_timeseries
        result = get_timeseries(in_memory_db, days=7)
        assert len(result) == 7

    def test_timeseries_1_day_returns_1_item(self, in_memory_db):
        from app.services.analytics.analytics_service import get_timeseries
        result = get_timeseries(in_memory_db, days=1)
        assert len(result) == 1

    def test_timeseries_30_days_returns_30_items(self, in_memory_db):
        from app.services.analytics.analytics_service import get_timeseries
        result = get_timeseries(in_memory_db, days=30)
        assert len(result) == 30

    def test_timeseries_today_counts_seeded_data(self, in_memory_db):
        """
        The in_memory_db fixture seeds data right now (today),
        so the last entry (today) must have non-zero counts.
        """
        from app.services.analytics.analytics_service import get_timeseries
        result = get_timeseries(in_memory_db, days=7)
        today_entry = result[-1]  # oldest → newest, last = today
        # 3 assistant messages seeded (2 gemini + 1 fallback)
        assert today_entry["ai_total"] == 3, \
            f"Expected 3 AI responses today, got {today_entry['ai_total']}"
        assert today_entry["gemini"]   == 2
        assert today_entry["fallback"] == 1

    def test_timeseries_empty_db_returns_zeros(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.db.base import Base
        import app.models  # noqa: F401
        from app.services.analytics.analytics_service import get_timeseries

        engine = create_engine("sqlite:///:memory:",
                               connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        try:
            result = get_timeseries(db, days=7)
            assert len(result) == 7
            for entry in result:
                assert entry["ai_total"] == 0
                assert entry["documents"] == 0
                assert entry["users"] == 0
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)

    def test_timeseries_dates_ascending(self, in_memory_db):
        from app.services.analytics.analytics_service import get_timeseries
        result = get_timeseries(in_memory_db, days=7)
        dates = [e["date"] for e in result]
        assert dates == sorted(dates)
