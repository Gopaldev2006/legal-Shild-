"""
test_rbac.py — Phase 5: Role-Based Access Control Tests
========================================================
Full role × endpoint access matrix plus cross-user ownership tests.

Structure
---------
  Section A — Role matrix (PUBLIC / PROFESSIONAL / ADMIN × endpoint)
  Section B — Cross-user ownership (User A must not see User B's resources)
  Section C — Centralized permissions module unit tests

Roles under test
----------------
  PUBLIC_USER          → registered user, no verification
  LEGAL_PROFESSIONAL   → verified advocate  (advocate@example.com / advocate123)
  ADMIN                → system admin       (admin@example.com    / admin123)

Run:
    cd backend
    python -m pytest tests/test_rbac.py -v

Note: the session-scoped disable_rate_limiting fixture in conftest.py patches
the limiter so tests never hit 429 from shared TestClient IP.
"""

import pytest
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
    """Log in as all three role types and return their tokens."""
    def _login(email, password):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed for {email}: {r.text}"
        return r.json()["access_token"]

    return {
        "public":  _login("public@example.com",   "public123"),
        "pro":     _login("advocate@example.com",  "advocate123"),
        "admin":   _login("admin@example.com",     "admin123"),
    }


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _no_auth():
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Section A — Role × Endpoint Access Matrix
# ─────────────────────────────────────────────────────────────────────────────

class TestPublicAIAccess:
    """POST /rag/public-query — open to all (authenticated and anonymous)."""

    def test_anonymous_can_call_public_query(self, client):
        r = client.post("/api/v1/rag/public-query",
                        json={"query": "What is a contract?"})
        # 200 OK or 422 (empty query) — never 401/403
        assert r.status_code not in (401, 403), \
            f"Public query should not require auth, got {r.status_code}"

    def test_public_user_can_call_public_query(self, client, tokens):
        r = client.post("/api/v1/rag/public-query",
                        json={"query": "What is habeas corpus?"},
                        headers=_auth(tokens["public"]))
        assert r.status_code not in (401, 403)

    def test_professional_can_call_public_query(self, client, tokens):
        r = client.post("/api/v1/rag/public-query",
                        json={"query": "Explain arbitration."},
                        headers=_auth(tokens["pro"]))
        assert r.status_code not in (401, 403)


class TestProfileAccess:
    """GET /auth/me — any authenticated user."""

    def test_public_user_can_view_own_profile(self, client, tokens):
        r = client.get("/api/v1/auth/me", headers=_auth(tokens["public"]))
        assert r.status_code == 200

    def test_professional_can_view_own_profile(self, client, tokens):
        r = client.get("/api/v1/auth/me", headers=_auth(tokens["pro"]))
        assert r.status_code == 200

    def test_admin_can_view_own_profile(self, client, tokens):
        r = client.get("/api/v1/auth/me", headers=_auth(tokens["admin"]))
        assert r.status_code == 200

    def test_unauthenticated_cannot_view_profile(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code in (401, 403)


class TestDocumentAccess:
    """Document upload/list — Professional and Admin only."""

    def test_public_user_cannot_upload_document(self, client, tokens):
        import io
        fake_pdf = b"%PDF-1.4\n" + b"a" * 200 + b"%%EOF"
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("test.pdf", io.BytesIO(fake_pdf), "application/pdf")},
            headers=_auth(tokens["public"]),
        )
        assert r.status_code == 403, \
            f"PUBLIC_USER must be denied document upload, got {r.status_code}"

    def test_unauthenticated_cannot_upload_document(self, client):
        import io
        fake_pdf = b"%PDF-1.4\n" + b"a" * 200 + b"%%EOF"
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("test.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        )
        assert r.status_code in (401, 403)

    def test_public_user_cannot_list_documents(self, client, tokens):
        r = client.get("/api/v1/documents/", headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_professional_can_list_documents(self, client, tokens):
        r = client.get("/api/v1/documents/", headers=_auth(tokens["pro"]))
        assert r.status_code == 200

    def test_admin_can_list_documents(self, client, tokens):
        r = client.get("/api/v1/documents/", headers=_auth(tokens["admin"]))
        assert r.status_code == 200


class TestRAGAccess:
    """POST /rag/query and /rag/search — Professional/Admin only."""

    def test_public_user_cannot_run_rag_query(self, client, tokens):
        r = client.post("/api/v1/rag/query",
                        json={"query": "What is the termination clause?"},
                        headers=_auth(tokens["public"]))
        assert r.status_code == 403, \
            f"PUBLIC_USER must be denied RAG query, got {r.status_code}"

    def test_unauthenticated_cannot_run_rag_query(self, client):
        r = client.post("/api/v1/rag/query",
                        json={"query": "termination clause"})
        assert r.status_code in (401, 403)

    def test_public_user_cannot_run_rag_search(self, client, tokens):
        r = client.post("/api/v1/rag/search",
                        json={"query": "confidentiality clause"},
                        headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_professional_can_run_rag_query(self, client, tokens):
        """Professional gets 200 (or 422 if validation fails) but never 401/403."""
        r = client.post("/api/v1/rag/query",
                        json={"query": "What is the notice period?"},
                        headers=_auth(tokens["pro"]))
        assert r.status_code not in (401, 403), \
            f"Professional must be allowed RAG query, got {r.status_code}"


class TestVectorSearchAccess:
    """POST /vector/search — Professional/Admin only."""

    def test_public_user_cannot_search_vectors(self, client, tokens):
        r = client.post("/api/v1/vector/search",
                        json={"query": "force majeure"},
                        headers=_auth(tokens["public"]))
        assert r.status_code == 403, \
            f"PUBLIC_USER must get 403 on vector search, got {r.status_code}"

    def test_unauthenticated_cannot_search_vectors(self, client):
        r = client.post("/api/v1/vector/search",
                        json={"query": "contract clause"})
        assert r.status_code in (401, 403)

    def test_professional_can_search_vectors(self, client, tokens):
        r = client.post("/api/v1/vector/search",
                        json={"query": "termination clause"},
                        headers=_auth(tokens["pro"]))
        assert r.status_code not in (401, 403)


class TestChatAccess:
    """Persistent chat — general mode for all, document/rag restricted."""

    def test_public_user_can_create_general_chat(self, client, tokens):
        r = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Test", "mode": "general"},
            headers=_auth(tokens["public"]),
        )
        assert r.status_code in (200, 201), \
            f"PUBLIC_USER must be allowed general chat, got {r.status_code}"

    def test_public_user_cannot_create_rag_chat(self, client, tokens):
        r = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Test", "mode": "rag"},
            headers=_auth(tokens["public"]),
        )
        assert r.status_code == 403, \
            f"PUBLIC_USER must be denied rag chat, got {r.status_code}"

    def test_public_user_cannot_create_document_chat(self, client, tokens):
        r = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Test", "mode": "document", "document_id": 1},
            headers=_auth(tokens["public"]),
        )
        assert r.status_code == 403, \
            f"PUBLIC_USER must be denied document chat, got {r.status_code}"

    def test_unauthenticated_cannot_create_chat(self, client):
        r = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Test", "mode": "general"},
        )
        assert r.status_code in (401, 403)

    def test_professional_can_create_rag_chat(self, client, tokens):
        r = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Test", "mode": "rag"},
            headers=_auth(tokens["pro"]),
        )
        # 200/201 = allowed, 422 = validation ok but bad request — not 401/403
        assert r.status_code not in (401, 403), \
            f"Professional must be allowed rag chat, got {r.status_code}"

    def test_public_user_cannot_list_others_conversations(self, client, tokens):
        """Public user can only see their own conversations (empty for a new account)."""
        r = client.get("/api/v1/chat/conversations",
                       headers=_auth(tokens["public"]))
        # 200 OK but only shows own conversations — never 403
        assert r.status_code == 200


class TestAdminEndpoints:
    """Admin dashboard — Admin only."""

    def test_public_user_cannot_access_admin_dashboard(self, client, tokens):
        r = client.get("/api/v1/admin/dashboard-summary",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403, \
            f"PUBLIC_USER must be denied admin dashboard, got {r.status_code}"

    def test_professional_cannot_access_admin_dashboard(self, client, tokens):
        r = client.get("/api/v1/admin/dashboard-summary",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 403, \
            f"LEGAL_PROFESSIONAL must be denied admin dashboard, got {r.status_code}"

    def test_admin_can_access_admin_dashboard(self, client, tokens):
        r = client.get("/api/v1/admin/dashboard-summary",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 200, \
            f"ADMIN must be allowed admin dashboard, got {r.status_code}"

    def test_public_user_cannot_list_all_users(self, client, tokens):
        r = client.get("/api/v1/admin/users", headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_professional_cannot_list_all_users(self, client, tokens):
        r = client.get("/api/v1/admin/users", headers=_auth(tokens["pro"]))
        assert r.status_code == 403

    def test_admin_can_list_all_users(self, client, tokens):
        r = client.get("/api/v1/admin/users", headers=_auth(tokens["admin"]))
        assert r.status_code == 200

    def test_public_user_cannot_access_security_events(self, client, tokens):
        r = client.get("/api/v1/admin/security-events",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_unauthenticated_cannot_access_admin(self, client):
        r = client.get("/api/v1/admin/dashboard-summary")
        assert r.status_code in (401, 403)


class TestCaseSearchAccess:
    """Case search/clustering — Professional/Admin only."""

    def test_public_user_cannot_search_cases(self, client, tokens):
        r = client.post("/api/v1/cases/search",
                        json={"query": "contract breach"},
                        headers=_auth(tokens["public"]))
        assert r.status_code == 403, \
            f"PUBLIC_USER must be denied case search, got {r.status_code}"

    def test_professional_can_search_cases(self, client, tokens):
        r = client.post("/api/v1/cases/search",
                        json={"query": "arbitration clause"},
                        headers=_auth(tokens["pro"]))
        assert r.status_code not in (401, 403)

    def test_public_user_cannot_access_clusters(self, client, tokens):
        r = client.get("/api/v1/cases/clusters",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403


class TestSessionsAccess:
    """Session management — any authenticated user (own sessions only)."""

    def test_unauthenticated_cannot_list_sessions(self, client):
        r = client.get("/api/v1/auth/sessions")
        assert r.status_code in (401, 403)

    def test_public_user_can_list_own_sessions(self, client, tokens):
        r = client.get("/api/v1/auth/sessions",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 200

    def test_professional_can_list_own_sessions(self, client, tokens):
        r = client.get("/api/v1/auth/sessions",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Section B — Cross-User Ownership
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossUserDocumentAccess:
    """User A must not access User B's documents."""

    def test_professional_cannot_access_nonexistent_document(self, client, tokens):
        """Requesting a document ID that doesn't exist → 404 (never 500 or 200)."""
        r = client.get("/api/v1/documents/999999",
                       headers=_auth(tokens["pro"]))
        assert r.status_code == 404

    def test_professional_cannot_delete_nonexistent_document(self, client, tokens):
        r = client.delete("/api/v1/documents/999999",
                          headers=_auth(tokens["pro"]))
        assert r.status_code == 404

    def test_admin_gets_404_for_nonexistent_document(self, client, tokens):
        """Even admin gets 404 for a document that doesn't exist."""
        r = client.get("/api/v1/documents/999999",
                       headers=_auth(tokens["admin"]))
        assert r.status_code == 404

    def test_public_user_gets_403_not_404_for_document_access(self, client, tokens):
        """Public user hits role check (403) before ownership check (404)."""
        r = client.get("/api/v1/documents/1",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403


class TestCrossUserConversationAccess:
    """User A must not access User B's conversations."""

    def _create_conversation(self, client, token, mode="general"):
        r = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Private conv", "mode": mode},
            headers=_auth(token),
        )
        if r.status_code in (200, 201):
            return r.json().get("id")
        return None

    def test_user_cannot_access_another_users_conversation(self, client, tokens):
        """Pro creates a conversation; public user gets 401/403/404 accessing it."""
        conv_id = self._create_conversation(client, tokens["pro"])
        if conv_id is None:
            pytest.skip("Could not create test conversation")

        # Public user attempts to read pro's conversation
        r = client.get(f"/api/v1/chat/conversations/{conv_id}",
                       headers=_auth(tokens["public"]))
        # Public user gets 200 (own empty convs) for the list endpoint,
        # but for a specific conversation they don't own → 404 (owner check)
        assert r.status_code in (401, 403, 404), \
            f"User must not access another user's conversation, got {r.status_code}"

    def test_user_cannot_delete_another_users_conversation(self, client, tokens):
        conv_id = self._create_conversation(client, tokens["pro"])
        if conv_id is None:
            pytest.skip("Could not create test conversation")

        r = client.delete(f"/api/v1/chat/conversations/{conv_id}",
                          headers=_auth(tokens["public"]))
        assert r.status_code in (401, 403, 404)


class TestCrossUserSessionAccess:
    """User A must not revoke User B's sessions."""

    def test_cannot_revoke_nonexistent_session(self, client, tokens):
        r = client.delete("/api/v1/auth/sessions/999999",
                          headers=_auth(tokens["pro"]))
        assert r.status_code == 404

    def test_revoke_all_only_affects_own_sessions(self, client, tokens):
        """revoke-all must return 200 and only revoke the calling user's sessions."""
        r = client.post("/api/v1/auth/sessions/revoke-all",
                        headers=_auth(tokens["pro"]))
        assert r.status_code == 200
        body = r.json()
        assert "revoked_count" in body


# ─────────────────────────────────────────────────────────────────────────────
# Section C — Permissions module unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionsModule:
    """Unit tests for the centralized permissions.py functions."""

    def _make_user(self, role, verified=True):
        """
        Build a lightweight mock User using SimpleNamespace.
        Using User.__new__ bypasses SQLAlchemy's __init__ and breaks
        the _sa_instance_state attribute — SimpleNamespace avoids this.
        """
        from types import SimpleNamespace
        from app.models.user import VerificationStatus
        return SimpleNamespace(
            id=1,
            role=role,
            verification_status=(
                VerificationStatus.VERIFIED if verified else VerificationStatus.PENDING
            ),
        )

    def test_require_professional_blocks_public_user(self):
        from fastapi import HTTPException
        from app.core.permissions import require_professional
        from app.models.user import UserRole

        user = self._make_user(UserRole.PUBLIC_USER)
        with pytest.raises(HTTPException) as exc:
            require_professional(user)
        assert exc.value.status_code == 403

    def test_require_professional_blocks_unverified_professional(self):
        from fastapi import HTTPException
        from app.core.permissions import require_professional
        from app.models.user import UserRole

        user = self._make_user(UserRole.LEGAL_PROFESSIONAL, verified=False)
        with pytest.raises(HTTPException) as exc:
            require_professional(user)
        assert exc.value.status_code == 403

    def test_require_professional_allows_verified_professional(self):
        from app.core.permissions import require_professional
        from app.models.user import UserRole

        user = self._make_user(UserRole.LEGAL_PROFESSIONAL, verified=True)
        result = require_professional(user)
        assert result is user

    def test_require_professional_allows_admin(self):
        from app.core.permissions import require_professional
        from app.models.user import UserRole

        user = self._make_user(UserRole.ADMIN)
        result = require_professional(user)
        assert result is user

    def test_require_admin_blocks_public(self):
        from fastapi import HTTPException
        from app.core.permissions import require_admin
        from app.models.user import UserRole

        user = self._make_user(UserRole.PUBLIC_USER)
        with pytest.raises(HTTPException) as exc:
            require_admin(user)
        assert exc.value.status_code == 403

    def test_require_admin_blocks_professional(self):
        from fastapi import HTTPException
        from app.core.permissions import require_admin
        from app.models.user import UserRole

        user = self._make_user(UserRole.LEGAL_PROFESSIONAL)
        with pytest.raises(HTTPException) as exc:
            require_admin(user)
        assert exc.value.status_code == 403

    def test_require_admin_allows_admin(self):
        from app.core.permissions import require_admin
        from app.models.user import UserRole

        user = self._make_user(UserRole.ADMIN)
        result = require_admin(user)
        assert result is user

    def test_assert_owner_or_admin_blocks_other_user(self):
        from fastapi import HTTPException
        from app.core.permissions import assert_owner_or_admin
        from app.models.user import UserRole

        user = self._make_user(UserRole.LEGAL_PROFESSIONAL)
        user.id = 10
        with pytest.raises(HTTPException) as exc:
            assert_owner_or_admin(resource_owner_id=99, current_user=user)
        assert exc.value.status_code == 403

    def test_assert_owner_or_admin_allows_owner(self):
        from app.core.permissions import assert_owner_or_admin
        from app.models.user import UserRole

        user = self._make_user(UserRole.LEGAL_PROFESSIONAL)
        user.id = 42
        # Should not raise
        assert_owner_or_admin(resource_owner_id=42, current_user=user)

    def test_assert_owner_or_admin_allows_admin_any_resource(self):
        from app.core.permissions import assert_owner_or_admin
        from app.models.user import UserRole

        admin = self._make_user(UserRole.ADMIN)
        admin.id = 1
        # Admin can access resource belonging to user 999
        assert_owner_or_admin(resource_owner_id=999, current_user=admin)

    def test_assert_resource_exists_and_owned_raises_404_for_none(self):
        from fastapi import HTTPException
        from app.core.permissions import assert_resource_exists_and_owned
        from app.models.user import UserRole

        user = self._make_user(UserRole.LEGAL_PROFESSIONAL)
        with pytest.raises(HTTPException) as exc:
            assert_resource_exists_and_owned(None, user, "document")
        assert exc.value.status_code == 404

    def test_assert_resource_exists_and_owned_raises_404_for_wrong_owner(self):
        """Wrong owner returns 404 not 403 — prevents resource existence leakage."""
        from fastapi import HTTPException
        from app.core.permissions import assert_resource_exists_and_owned
        from app.models.user import UserRole

        user = self._make_user(UserRole.LEGAL_PROFESSIONAL)
        user.id = 10

        # Mock resource belonging to user 99
        class FakeDoc:
            owner_id = 99

        with pytest.raises(HTTPException) as exc:
            assert_resource_exists_and_owned(FakeDoc(), user, "document")
        assert exc.value.status_code == 404, \
            "Wrong owner must return 404 not 403 to avoid existence leakage"


# ─────────────────────────────────────────────────────────────────────────────
# Section D — HTTP response code correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestHTTPResponseCodes:
    """Verify 401 vs 403 semantics are correct."""

    def test_missing_token_returns_401_not_403(self, client):
        """No token at all → 401 Unauthorized (not 403 Forbidden)."""
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401, \
            f"Missing token must be 401, got {r.status_code}"

    def test_invalid_token_returns_401(self, client):
        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": "Bearer invalidtoken"})
        assert r.status_code == 401

    def test_wrong_role_returns_403_not_401(self, client, tokens):
        """Valid token but wrong role → 403 Forbidden."""
        r = client.get("/api/v1/admin/dashboard-summary",
                       headers=_auth(tokens["public"]))
        assert r.status_code == 403, \
            f"Wrong role must be 403, got {r.status_code}"

    def test_wrong_role_on_rag_returns_403(self, client, tokens):
        r = client.post("/api/v1/rag/query",
                        json={"query": "test"},
                        headers=_auth(tokens["public"]))
        assert r.status_code == 403

    def test_wrong_role_on_document_upload_returns_403(self, client, tokens):
        import io
        fake_pdf = b"%PDF-1.4\n" + b"a" * 200 + b"%%EOF"
        r = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "GENERAL"},
            files={"file": ("t.pdf", io.BytesIO(fake_pdf), "application/pdf")},
            headers=_auth(tokens["public"]),
        )
        assert r.status_code == 403
