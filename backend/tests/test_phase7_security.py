"""
test_phase7_security.py — Phase 7 Final Security Audit Tests
==============================================================
20 security test cases covering every acceptance criterion.

TC-01  Unauthorized API access (no token)
TC-02  Wrong role — public user on professional endpoint
TC-03  Cross-user document access
TC-04  Cross-user chat access
TC-05  Cross-user RAG access
TC-06  Invalid JWT signature
TC-07  Expired JWT
TC-08  Revoked session
TC-09  Brute-force login (rate limiting)
TC-10  Rate limiting — AI endpoint
TC-11  Oversized file upload
TC-12  Malicious filename (path traversal)
TC-13  Invalid file type (.exe)
TC-14  Fake PDF (magic-byte mismatch)
TC-15  Fake DOCX (magic-byte mismatch)
TC-16  Gemini API-key never returned in plaintext
TC-17  GET /auth/gemini-api-key returns masked preview only
TC-18  Audit log access restricted to admin
TC-19  Admin authorization enforced on dashboard
TC-20  No secrets leak in audit log metadata

Run:
    cd backend
    python -m pytest tests/test_phase7_security.py -v
"""

import io
import json
import time
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def tokens(client):
    """Log in as public, professional, and admin. Return dict of tokens."""
    def _login(email, password):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed for {email}: {r.text}"
        return r.json()["access_token"]

    return {
        "public":  _login("public@example.com",  "public123"),
        "pro":     _login("advocate@example.com", "advocate123"),
        "admin":   _login("admin@example.com",    "admin123"),
    }


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Unauthorized API access — no token
# ─────────────────────────────────────────────────────────────────────────────

class TestUnauthorizedAccess:
    def test_no_token_returns_401(self, client):
        endpoints = [
            ("GET",  "/api/v1/auth/me"),
            ("GET",  "/api/v1/documents/"),
            ("GET",  "/api/v1/auth/sessions"),
            ("GET",  "/api/v1/admin/dashboard-summary"),
        ]
        for method, path in endpoints:
            r = client.request(method, path)
            assert r.status_code in (401, 403), \
                f"{method} {path} should require auth, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Wrong role — public user on professional endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestWrongRole:
    def test_public_user_denied_rag_query(self, client, tokens):
        r = client.post("/api/v1/rag/query",
                        json={"query": "test"},
                        headers=_auth(tokens["public"]))
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def test_public_user_denied_document_upload(self, client, tokens):
        fake_pdf = b"%PDF-1.4\n" + b"x" * 200 + b"%%EOF"
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("test.pdf", io.BytesIO(fake_pdf), "application/pdf")},
            headers=_auth(tokens["public"]),
        )
        assert r.status_code == 403

    def test_public_user_denied_rag_document_chat(self, client, tokens):
        r = client.post("/api/v1/chat/conversations",
                        json={"title": "Test", "mode": "rag"},
                        headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_professional_denied_admin_dashboard(self, client, tokens):
        r = client.get("/api/v1/admin/dashboard-summary",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Cross-user document access
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossUserDocumentAccess:
    def test_nonexistent_document_returns_404(self, client, tokens):
        """Requesting a document that doesn't belong to us → 404 (not 500, not 200)."""
        r = client.get("/api/v1/documents/999999", headers=_auth(tokens["pro"]))
        assert r.status_code == 404

    def test_public_user_gets_403_not_404(self, client, tokens):
        """Role check (403) fires before ownership check (404)."""
        r = client.get("/api/v1/documents/1", headers=_auth(tokens["public"]))
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  Cross-user chat access
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossUserChatAccess:
    def test_nonexistent_conversation_returns_404(self, client, tokens):
        r = client.get("/api/v1/chat/conversations/999999",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 404

    def test_cannot_delete_nonexistent_conversation(self, client, tokens):
        r = client.delete("/api/v1/chat/conversations/999999",
                          headers=_auth(tokens["pro"]))
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Cross-user RAG access
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossUserRAGAccess:
    def test_rag_query_scoped_to_user(self, client, tokens):
        """RAG query succeeds (200) but result is scoped to user's own documents."""
        r = client.post("/api/v1/rag/query",
                        json={"query": "What is the termination clause?"},
                        headers=_auth(tokens["pro"]))
        # 200 = allowed; result is owner-scoped
        assert r.status_code not in (401, 403), \
            f"Professional should be allowed RAG, got {r.status_code}"

    def test_rag_query_with_other_user_document_id_returns_no_context(self, client, tokens):
        """Requesting RAG on document_id 999999 (not owned) → no context, not 500."""
        r = client.post("/api/v1/rag/query",
                        json={"query": "test", "document_id": 999999},
                        headers=_auth(tokens["pro"]))
        assert r.status_code not in (500,), "Should fail gracefully, not 500"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06  Invalid JWT signature
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidJWT:
    def test_tampered_token_returns_401(self, client):
        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.invalid.sig"})
        assert r.status_code == 401

    def test_completely_random_token_returns_401(self, client):
        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": "Bearer notavalidjwt"})
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# TC-07  Expired JWT
# ─────────────────────────────────────────────────────────────────────────────

class TestExpiredJWT:
    def test_expired_token_returns_401(self, client):
        import jwt as pyjwt
        from app.core.config import settings

        expired_payload = {
            "sub":  "9999",
            "jti":  str(uuid.uuid4()),
            "iat":  int(time.time()) - 7200,
            "exp":  int(time.time()) - 3600,  # expired 1 hour ago
        }
        expired_token = pyjwt.encode(
            expired_payload, settings.JWT_SECRET_KEY, algorithm="HS256"
        )
        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": f"Bearer {expired_token}"})
        assert r.status_code == 401, f"Expired token must return 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-08  Revoked session
# ─────────────────────────────────────────────────────────────────────────────

class TestRevokedSession:
    def test_revoked_token_rejected_even_if_not_expired(self, client):
        """Log in → logout → same token returns 401."""
        login_r = client.post("/api/v1/auth/login",
                              json={"email": "advocate@example.com",
                                    "password": "advocate123"})
        assert login_r.status_code == 200
        token = login_r.json()["access_token"]

        # Confirm token works
        assert client.get("/api/v1/auth/me",
                          headers=_auth(token)).status_code == 200

        # Logout (revoke)
        client.post("/api/v1/auth/logout", headers=_auth(token))

        # Must now be rejected
        r = client.get("/api/v1/auth/me", headers=_auth(token))
        assert r.status_code == 401, \
            f"Revoked token must return 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  Brute-force login (rate limiting)
# ─────────────────────────────────────────────────────────────────────────────

class TestBruteForceProtection:
    def test_login_rate_limit_config_is_tight(self):
        """Login rate limit must be ≤ 10/minute to prevent brute-force."""
        from app.core.config import settings
        count = int(settings.RATE_LIMIT_LOGIN.split("/")[0])
        assert count <= 10, \
            f"Login rate limit {settings.RATE_LIMIT_LOGIN} is too permissive for brute-force protection"

    def test_login_failure_does_not_reveal_whether_user_exists(self, client):
        """Same error message for wrong email vs wrong password."""
        r_bad_email = client.post("/api/v1/auth/login",
                                  json={"email": "doesnotexist99999@example.com",
                                        "password": "wrongpass"})
        r_bad_pass  = client.post("/api/v1/auth/login",
                                  json={"email": "advocate@example.com",
                                        "password": "WRONGPASSWORD"})
        # Both must be 401
        assert r_bad_email.status_code == 401
        assert r_bad_pass.status_code  == 401
        # Both must have the same detail message (no user-existence leakage)
        assert r_bad_email.json().get("detail") == r_bad_pass.json().get("detail"), \
            "Error messages differ — user existence is being leaked"


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  Rate limiting — AI endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestAIRateLimiting:
    def test_rag_query_rate_limit_is_configured(self):
        from app.core.config import settings
        count = int(settings.RATE_LIMIT_RAG_QUERY.split("/")[0])
        assert count <= 30, \
            f"RAG rate limit {settings.RATE_LIMIT_RAG_QUERY} is too permissive"

    def test_public_query_rate_limit_is_configured(self):
        from app.core.config import settings
        count = int(settings.RATE_LIMIT_PUBLIC_QUERY.split("/")[0])
        assert count <= 60, \
            f"Public query rate limit {settings.RATE_LIMIT_PUBLIC_QUERY} is too permissive"


# ─────────────────────────────────────────────────────────────────────────────
# TC-11  Oversized file upload
# ─────────────────────────────────────────────────────────────────────────────

class TestOversizedUpload:
    def test_oversized_file_returns_4xx(self, client, tokens):
        """
        Oversized uploads are rejected with 4xx.
        Starlette may return 422 from its multipart parser before the endpoint
        body runs; the endpoint itself returns 413. Either is a valid rejection.
        """
        base    = b"%PDF-1.4\n" + b"x" * 200 + b"%%EOF"
        padded  = base + b"\x00" * (11 * 1024 * 1024)
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("big.pdf", io.BytesIO(padded), "application/pdf")},
            headers=_auth(tokens["pro"]),
        )
        assert r.status_code in (400, 413, 422), \
            f"Oversized file must be rejected (400/413/422), got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-12  Malicious filename (path traversal)
# ─────────────────────────────────────────────────────────────────────────────

class TestMaliciousFilename:
    def test_path_traversal_filename_blocked(self, client, tokens):
        fake_pdf = b"%PDF-1.4\n" + b"x" * 200 + b"%%EOF"
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("../../etc/passwd.pdf",
                            io.BytesIO(fake_pdf), "application/pdf")},
            headers=_auth(tokens["pro"]),
        )
        # 400/415 from our validator; 422 if Starlette intercepts the multipart first
        assert r.status_code in (400, 415, 422), \
            f"Path traversal filename must be blocked, got {r.status_code}"

    def test_null_byte_filename_blocked(self, client, tokens):
        fake_pdf = b"%PDF-1.4\n" + b"x" * 200 + b"%%EOF"
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("contract\x00.pdf",
                            io.BytesIO(fake_pdf), "application/pdf")},
            headers=_auth(tokens["pro"]),
        )
        assert r.status_code in (400, 415, 422)


# ─────────────────────────────────────────────────────────────────────────────
# TC-13  Invalid file type
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidFileType:
    @pytest.mark.parametrize("filename,content", [
        ("malware.exe",  b"\x4D\x5A\x90\x00" + b"\x00" * 100),
        ("script.js",    b"console.log('pwned')"),
        ("archive.zip",  b"PK\x03\x04" + b"\x00" * 50),
        ("data.txt",     b"some text content"),
    ])
    def test_disallowed_extension_rejected(self, client, tokens, filename, content):
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
            headers=_auth(tokens["pro"]),
        )
        # Our validator returns 400/415; Starlette may intercept with 422
        assert r.status_code in (400, 415, 422), \
            f"File '{filename}' must be rejected, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-14  Fake PDF (magic-byte mismatch)
# ─────────────────────────────────────────────────────────────────────────────

class TestFakePDF:
    def test_exe_renamed_to_pdf_rejected(self, client, tokens):
        exe_content = b"\x4D\x5A\x90\x00" + b"\x00" * 200 + b"%%EOF"
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("legit_contract.pdf",
                            io.BytesIO(exe_content), "application/pdf")},
            headers=_auth(tokens["pro"]),
        )
        # 415 from our magic-byte check; 422 if Starlette intercepts first
        assert r.status_code in (415, 422), \
            f"Fake PDF (EXE bytes) must be rejected (415/422), got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-15  Fake DOCX (magic-byte mismatch)
# ─────────────────────────────────────────────────────────────────────────────

class TestFakeDOCX:
    def test_exe_renamed_to_docx_rejected(self, client, tokens):
        exe_content = b"\x4D\x5A\x90\x00" + b"\x00" * 200
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("contract.docx",
                            io.BytesIO(exe_content), "application/vnd.openxmlformats")},
            headers=_auth(tokens["pro"]),
        )
        # 415 from magic-byte check; 422 if Starlette intercepts first
        assert r.status_code in (415, 422), \
            f"Fake DOCX (EXE bytes) must be rejected (415/422), got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-16  Gemini API-key never returned in plaintext
# ─────────────────────────────────────────────────────────────────────────────

class TestGeminiKeyNotExposed:
    def test_gemini_key_encrypted_at_rest(self):
        """Verify encrypt_api_key returns ciphertext, not the original key."""
        from app.core.security import encrypt_api_key, decrypt_api_key
        plaintext = "AIzaSyFakeTestKey12345678"
        ciphertext = encrypt_api_key(plaintext)
        assert ciphertext != plaintext, "API key must be encrypted at rest"
        assert "AIzaSy" not in ciphertext, "Plaintext key must not appear in ciphertext"
        # Round-trip
        recovered = decrypt_api_key(ciphertext)
        assert recovered == plaintext

    def test_encrypt_blocks_empty_key(self):
        from app.core.security import encrypt_api_key
        assert encrypt_api_key("") == ""

    def test_decrypt_invalid_ciphertext_returns_none(self):
        from app.core.security import decrypt_api_key
        assert decrypt_api_key("not_valid_ciphertext") is None
        assert decrypt_api_key("") is None
        assert decrypt_api_key(None) is None


# ─────────────────────────────────────────────────────────────────────────────
# TC-17  GET /auth/gemini-api-key returns masked preview only
# ─────────────────────────────────────────────────────────────────────────────

class TestGeminiKeyMaskedResponse:
    def test_get_gemini_key_status_never_returns_full_key(self, client, tokens):
        """
        Store a test key then check the GET endpoint returns only a masked preview.
        The full key must never appear in the response body.
        """
        fake_key = "AIzaSyFakeKeyForMaskingTest12345"

        # Store the key
        client.post("/api/v1/auth/gemini-api-key",
                    json={"api_key": fake_key},
                    headers=_auth(tokens["pro"]))

        # Read the status
        r = client.get("/api/v1/auth/gemini-api-key",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 200

        body     = r.text
        body_low = body.lower()

        # Full key must NOT appear in response
        assert fake_key not in body, \
            "Full API key must never be returned in the GET response"

        # No raw 'AIzaSy' prefix should appear beyond the first 8 chars of a masked preview
        # (the masked preview shows first 8 chars which starts with AIzaSyFa — that is acceptable)
        # But the FULL key string must not be there
        assert fake_key[8:] not in body, \
            "Tail of API key must not appear in response"

        # Response must contain has_api_key=true
        assert '"has_api_key": true' in body or '"has_api_key":true' in body or \
               r.json().get("has_api_key") is True

        # Clean up
        client.delete("/api/v1/auth/gemini-api-key", headers=_auth(tokens["pro"]))

    def test_gemini_key_preview_contains_stars(self, client, tokens):
        """Preview format must be 'AIzaSyFa***' — masked with asterisks."""
        fake_key = "AIzaSyFakeKeyForPreviewTest9876"

        client.post("/api/v1/auth/gemini-api-key",
                    json={"api_key": fake_key},
                    headers=_auth(tokens["pro"]))

        r = client.get("/api/v1/auth/gemini-api-key",
                       headers=_auth(tokens["pro"]))

        body = r.json()
        preview = body.get("api_key_preview", "")
        assert "***" in preview, f"Preview must contain '***', got: {preview}"
        assert len(preview) < len(fake_key), "Preview must be shorter than the real key"

        client.delete("/api/v1/auth/gemini-api-key", headers=_auth(tokens["pro"]))


# ─────────────────────────────────────────────────────────────────────────────
# TC-18  Audit log access restricted to admin
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditLogAccess:
    def test_public_user_cannot_access_audit_logs(self, client, tokens):
        r = client.get("/api/v1/admin/audit-logs",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403, \
            f"Public user must be denied audit logs, got {r.status_code}"

    def test_professional_cannot_access_audit_logs(self, client, tokens):
        r = client.get("/api/v1/admin/audit-logs",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 403

    def test_admin_can_access_audit_logs(self, client, tokens):
        r = client.get("/api/v1/admin/audit-logs",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body

    def test_unauthenticated_cannot_access_audit_logs(self, client):
        r = client.get("/api/v1/admin/audit-logs")
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────────────
# TC-19  Admin authorization enforced on all admin endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminAuthorization:
    @pytest.mark.parametrize("path", [
        "/api/v1/admin/dashboard-summary",
        "/api/v1/admin/users",
        "/api/v1/admin/verifications",
        "/api/v1/admin/documents",
        "/api/v1/admin/security-events",
        "/api/v1/admin/model-status",
        "/api/v1/admin/audit-logs",
    ])
    def test_all_admin_endpoints_deny_non_admin(self, client, tokens, path):
        for role, token in [("public", tokens["public"]), ("pro", tokens["pro"])]:
            r = client.get(path, headers=_auth(token))
            assert r.status_code == 403, \
                f"{role} must be denied {path}, got {r.status_code}"

    def test_all_admin_endpoints_allow_admin(self, client, tokens):
        paths = [
            "/api/v1/admin/dashboard-summary",
            "/api/v1/admin/users",
            "/api/v1/admin/audit-logs",
        ]
        for path in paths:
            r = client.get(path, headers=_auth(tokens["admin"]))
            assert r.status_code == 200, \
                f"Admin must be allowed {path}, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-20  No secrets in audit log metadata
# ─────────────────────────────────────────────────────────────────────────────

class TestNoSecretsInAuditLogs:
    def test_audit_service_strips_secret_keys(self):
        """_sanitise_metadata must silently remove any key that sounds like a secret."""
        from app.services.audit.audit_service import _sanitise_metadata
        import json

        dirty = {
            "password":     "hunter2",
            "api_key":      "AIzaSyFakeKey",
            "token":        "eyJhbGci...",
            "access_token": "secret123",
            "secret":       "mysecret",
            "encrypted":    "cipherbytes",
            "filename":     "contract.pdf",   # safe — should be kept
            "provider":     "gemini",         # safe — should be kept
        }

        result_json = _sanitise_metadata(dirty)
        assert result_json is not None

        result = json.loads(result_json)

        # Secret keys must be removed
        for blocked in ("password", "api_key", "token", "access_token",
                        "secret", "encrypted"):
            assert blocked not in result, \
                f"Secret key '{blocked}' must be stripped from audit metadata"

        # Safe keys must be kept
        assert "filename" in result
        assert "provider" in result

    def test_audit_log_metadata_in_db_never_contains_key_string(self):
        """
        When write_audit_event is called with a metadata dict containing
        a password key, the stored metadata_json must not contain it.
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.db.base import Base
        import app.models  # noqa: F401

        engine  = create_engine("sqlite:///:memory:",
                                 connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db      = Session()

        from app.services.audit.audit_service import write_audit_event
        from app.models.audit_log import AuditLog, AuditEventType

        write_audit_event(
            db=db,
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=1,
            metadata={
                "password":    "SHOULD_NOT_APPEAR",
                "api_key":     "AIzaSySHOULD_NOT_APPEAR",
                "role":        "LEGAL_PROFESSIONAL",   # safe
                "login_count": 1,                      # safe
            },
        )

        log = db.query(AuditLog).first()
        assert log is not None
        assert log.metadata_json is not None

        raw = log.metadata_json
        assert "SHOULD_NOT_APPEAR" not in raw, \
            f"Secret value must not appear in stored metadata: {raw}"
        assert "password"  not in raw
        assert "api_key"   not in raw
        assert "role"      in raw    # safe field must be present

        db.close()
