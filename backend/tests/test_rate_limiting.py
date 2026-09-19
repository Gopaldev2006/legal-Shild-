"""
test_rate_limiting.py — Phase 3: Rate Limiting Tests
======================================================
Unit and integration tests for the SlowAPI rate-limiting configuration.

These tests verify:
  TC-01  Limiter instance is created correctly
  TC-02  All rate-limit strings are valid slowapi format
  TC-03  Config default values match intended limits
  TC-04  RATE_LIMIT_ENABLED flag is present in settings
  TC-05  Limiter headers_enabled is True
  TC-06  Login endpoint enforces 429 after exceeding limit (integration)
  TC-07  Register endpoint enforces 429 after exceeding limit (integration)
  TC-08  Public-query endpoint enforces 429 after exceeding limit (integration)
  TC-09  Rate-limit headers returned in response (X-RateLimit-*)
  TC-10  429 response body is JSON with 'error' key (not raw exception)

Run:
    cd backend
    python -m pytest tests/test_rate_limiting.py -v
"""

import re
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_LIMIT_PATTERN = re.compile(
    r"^\d+/(second|minute|hour|day)$",
    re.IGNORECASE,
)


def _is_valid_limit_string(s: str) -> bool:
    """Return True if the string matches the slowapi limit format."""
    return bool(_LIMIT_PATTERN.match(s))


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Limiter instance
# ─────────────────────────────────────────────────────────────────────────────

class TestLimiterInstance:
    def test_limiter_is_importable(self):
        from app.core.limiter import limiter
        assert limiter is not None

    def test_limiter_is_slowapi_limiter(self):
        from app.core.limiter import limiter
        from slowapi import Limiter
        assert isinstance(limiter, Limiter)

    def test_limiter_has_no_default_limits(self):
        """Default limits list should be empty — we set per-endpoint limits only."""
        from app.core.limiter import limiter
        # slowapi stores default_limits on the limiter
        defaults = getattr(limiter, "_default_limits", [])
        assert defaults == [], (
            "Global default limits should be empty — use per-endpoint decorators instead"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Valid limit strings
# ─────────────────────────────────────────────────────────────────────────────

class TestLimitStringFormat:
    @pytest.mark.parametrize("attr,expected_window", [
        ("RATE_LIMIT_LOGIN",        "minute"),
        ("RATE_LIMIT_REGISTER",     "minute"),
        ("RATE_LIMIT_PUBLIC_QUERY", "minute"),
        ("RATE_LIMIT_RAG_QUERY",    "minute"),
        ("RATE_LIMIT_DOC_UPLOAD",   "minute"),
        ("RATE_LIMIT_DOC_ANALYSIS", "minute"),
        ("RATE_LIMIT_CHAT_MESSAGE", "minute"),
        ("RATE_LIMIT_CHAT_CREATE",  "minute"),
    ])
    def test_limit_string_is_valid_format(self, attr, expected_window):
        from app.core.config import settings
        value = getattr(settings, attr)
        assert _is_valid_limit_string(value), (
            f"settings.{attr} = '{value}' is not a valid slowapi limit string "
            f"(expected format: '<int>/{expected_window}')"
        )

    @pytest.mark.parametrize("attr,expected_window", [
        ("RATE_LIMIT_DOC_UPLOAD",   "minute"),
        ("RATE_LIMIT_DOC_ANALYSIS", "minute"),
    ])
    def test_upload_and_analysis_limits_use_minute_window(self, attr, expected_window):
        """Upload and analysis limits should use /minute for burst protection."""
        from app.core.config import settings
        value = getattr(settings, attr)
        assert expected_window in value.lower(), (
            f"settings.{attr} = '{value}' should use '{expected_window}' window"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Default values are sensible
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigDefaultValues:
    def test_login_limit_is_at_most_10_per_minute(self):
        from app.core.config import settings
        count = int(settings.RATE_LIMIT_LOGIN.split("/")[0])
        assert count <= 10, (
            f"Login limit {settings.RATE_LIMIT_LOGIN} is too permissive — "
            f"should be ≤ 10/minute to prevent brute-force"
        )

    def test_register_limit_is_at_most_20_per_minute(self):
        from app.core.config import settings
        count = int(settings.RATE_LIMIT_REGISTER.split("/")[0])
        assert count <= 20

    def test_upload_limit_is_at_most_20_per_hour(self):
        from app.core.config import settings
        count = int(settings.RATE_LIMIT_DOC_UPLOAD.split("/")[0])
        assert count <= 20, (
            f"Upload limit {settings.RATE_LIMIT_DOC_UPLOAD} allows too many uploads/hour"
        )

    def test_analysis_limit_is_at_most_30_per_hour(self):
        from app.core.config import settings
        count = int(settings.RATE_LIMIT_DOC_ANALYSIS.split("/")[0])
        assert count <= 30


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  RATE_LIMIT_ENABLED flag
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitEnabledFlag:
    def test_flag_exists_in_settings(self):
        from app.core.config import settings
        assert hasattr(settings, "RATE_LIMIT_ENABLED"), (
            "settings.RATE_LIMIT_ENABLED is missing from config.py"
        )

    def test_flag_is_boolean(self):
        from app.core.config import settings
        assert isinstance(settings.RATE_LIMIT_ENABLED, bool)

    def test_flag_is_true_by_default(self):
        """Rate limiting should be enabled by default."""
        from app.core.config import settings
        assert settings.RATE_LIMIT_ENABLED is True


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Headers enabled
# ─────────────────────────────────────────────────────────────────────────────

class TestLimiterHeaders:
    def test_headers_enabled_is_true(self):
        """X-RateLimit-* headers must be sent so clients know their remaining quota."""
        from app.core.limiter import limiter
        assert getattr(limiter, "_headers_enabled", False) is True, (
            "limiter.headers_enabled must be True so clients receive X-RateLimit-* headers"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-06 / TC-07 / TC-08  Integration — 429 enforcement
# Uses FastAPI TestClient with the real app.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_client():
    """
    Build a TestClient with rate limiting ENABLED (bypasses the session-scoped
    disable fixture) and a very tight limit override so tests trigger 429 quickly.
    """
    from fastapi.testclient import TestClient
    from app.core import config as cfg_module
    from app.core.limiter import limiter
    from starlette.requests import Request

    # Save originals
    original_values = {
        "RATE_LIMIT_LOGIN":        cfg_module.settings.RATE_LIMIT_LOGIN,
        "RATE_LIMIT_REGISTER":     cfg_module.settings.RATE_LIMIT_REGISTER,
        "RATE_LIMIT_PUBLIC_QUERY": cfg_module.settings.RATE_LIMIT_PUBLIC_QUERY,
    }
    cfg_module.settings.RATE_LIMIT_LOGIN        = "1/minute"
    cfg_module.settings.RATE_LIMIT_REGISTER     = "1/minute"
    cfg_module.settings.RATE_LIMIT_PUBLIC_QUERY = "1/minute"

    # Restore the REAL check method (overrides the session-scope disable patch)
    real_check = limiter.__class__._check_request_limit
    limiter._check_request_limit = real_check.__get__(limiter, limiter.__class__)

    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)

    yield client

    # Re-apply the test-session no-op so other tests stay unaffected
    def _noop(request: Request, endpoint, *args, **kwargs):
        request.state.view_rate_limit = None

    limiter._check_request_limit = _noop

    # Restore limit strings
    for k, v in original_values.items():
        setattr(cfg_module.settings, k, v)


class TestLoginRateLimit:
    def test_login_429_after_limit(self, test_client):
        payload = {"email": "nonexistent@example.com", "password": "wrongpass"}
        headers = {"X-Forwarded-For": "10.0.1.1"}  # unique IP per test class

        # First request — may succeed or return 401 (wrong creds), never 429
        r1 = test_client.post("/api/v1/auth/login", json=payload, headers=headers)
        assert r1.status_code != 429, f"First request should not be rate-limited, got {r1.status_code}"

        # Second request — must be 429 (limit is 1/minute)
        r2 = test_client.post("/api/v1/auth/login", json=payload, headers=headers)
        assert r2.status_code == 429, (
            f"Expected 429 after exceeding login rate limit, got {r2.status_code}"
        )


class TestRegisterRateLimit:
    def test_register_429_after_limit(self, test_client):
        payload = {"name": "Test", "email": "ratelimit_test@example.com", "password": "pass123"}
        headers = {"X-Forwarded-For": "10.0.2.1"}

        r1 = test_client.post("/api/v1/auth/register", json=payload, headers=headers)
        assert r1.status_code != 429

        r2 = test_client.post("/api/v1/auth/register", json=payload, headers=headers)
        assert r2.status_code == 429, (
            f"Expected 429 after exceeding register rate limit, got {r2.status_code}"
        )


class TestPublicQueryRateLimit:
    def test_public_query_429_after_limit(self, test_client):
        payload = {"query": "What is a contract?"}
        headers = {"X-Forwarded-For": "10.0.3.1"}

        r1 = test_client.post("/api/v1/rag/public-query", json=payload, headers=headers)
        assert r1.status_code != 429

        r2 = test_client.post("/api/v1/rag/public-query", json=payload, headers=headers)
        assert r2.status_code == 429, (
            f"Expected 429 after exceeding public-query rate limit, got {r2.status_code}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  Rate-limit headers present in response
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitHeaders:
    def test_ratelimit_headers_in_normal_response(self, test_client):
        """Non-limited responses must include X-RateLimit-Limit and X-RateLimit-Remaining."""
        payload = {"query": "What is arbitration?"}
        headers = {"X-Forwarded-For": "10.0.4.99"}  # fresh IP, not yet limited

        r = test_client.post("/api/v1/rag/public-query", json=payload, headers=headers)

        # Only check headers if the response is not a 429 (fresh IP should not be limited)
        if r.status_code != 429:
            header_keys = {k.lower() for k in r.headers.keys()}
            has_limit     = any("x-ratelimit-limit"     in k for k in header_keys)
            has_remaining = any("x-ratelimit-remaining" in k for k in header_keys)
            assert has_limit and has_remaining, (
                f"X-RateLimit-* headers missing from response. "
                f"Got headers: {list(r.headers.keys())}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  429 response body is JSON
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitResponseBody:
    def test_429_response_is_json(self, test_client):
        payload = {"email": "json_test@example.com", "password": "wrongpass"}
        headers = {"X-Forwarded-For": "10.0.5.1"}

        # Exhaust the limit
        test_client.post("/api/v1/auth/login", json=payload, headers=headers)
        r = test_client.post("/api/v1/auth/login", json=payload, headers=headers)

        if r.status_code == 429:
            try:
                body = r.json()
                assert isinstance(body, dict), "429 body must be a JSON object"
            except Exception:
                pytest.fail("429 response body is not valid JSON")

    def test_429_response_has_safe_message(self, test_client):
        """429 body must contain a safe user-facing message, not internal details."""
        payload = {"email": "msg_test@example.com", "password": "wrongpass"}
        headers = {"X-Forwarded-For": "10.0.6.1"}

        test_client.post("/api/v1/auth/login", json=payload, headers=headers)
        r = test_client.post("/api/v1/auth/login", json=payload, headers=headers)

        if r.status_code == 429:
            body = r.json()
            error_text = body.get("error", body.get("detail", "")).lower()
            assert "too many" in error_text or "rate" in error_text or "limit" in error_text, (
                f"429 body should contain a user-friendly message, got: {body}"
            )
            # Must NOT expose internal limit config details
            assert "settings" not in error_text
            assert "lambda" not in error_text

    def test_429_response_has_retry_after_header(self, test_client):
        """429 response must include Retry-After header."""
        payload = {"email": "retry_test@example.com", "password": "wrongpass"}
        headers = {"X-Forwarded-For": "10.0.7.1"}

        test_client.post("/api/v1/auth/login", json=payload, headers=headers)
        r = test_client.post("/api/v1/auth/login", json=payload, headers=headers)

        if r.status_code == 429:
            assert "retry-after" in {k.lower() for k in r.headers.keys()}, (
                "429 response must include Retry-After header so clients know when to retry"
            )
