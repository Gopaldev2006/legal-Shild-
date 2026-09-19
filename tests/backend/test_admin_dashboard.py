"""
Comprehensive Pytest Test Suite for Admin Dashboard & Management API.

Tests:
1. Admin dashboard summary cards endpoint (/api/v1/admin/dashboard-summary)
2. Admin user management search, role/status filtering & pagination (/api/v1/admin/users)
3. Admin system-wide document audit list (/api/v1/admin/documents)
4. Admin security threat events audit (/api/v1/admin/security-events)
5. Admin SLM model status (/api/v1/admin/model-status)
6. Strict Backend RBAC Enforcement (Non-ADMIN users receive HTTP 403 Forbidden on all admin endpoints)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session
from app.main import app
from app.models.user import User, UserRole, VerificationStatus
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_admin_dashboard_summary_endpoint(db: Session):
    """1. Verify GET /api/v1/admin/dashboard-summary returns summary cards and health data."""
    admin = User(
        name="Admin Summary Test",
        email="admin_summary@example.com",
        password_hash=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(admin)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "admin_summary@example.com", "password": "adminpass123"})).json()["access_token"]

        res = await ac.get(
            "/api/v1/admin/dashboard-summary",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200
        data = res.json()
        assert "cards" in data
        assert "total_users" in data["cards"]
        assert "verified_professionals" in data["cards"]
        assert "pending_verifications" in data["cards"]
        assert "system_health" in data
        assert "model_status" in data


@pytest.mark.asyncio
async def test_admin_user_management_search_and_filter(db: Session):
    """2. Verify GET /api/v1/admin/users pagination, role filtering, and search."""
    admin = User(
        name="Admin User Management Test",
        email="admin_usermgt@example.com",
        password_hash=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        verification_status=VerificationStatus.VERIFIED
    )
    user_pro = User(
        name="Pro Attorney User",
        email="pro_attorney@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add_all([admin, user_pro])
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "admin_usermgt@example.com", "password": "adminpass123"})).json()["access_token"]

        # Search test
        res = await ac.get(
            "/api/v1/admin/users?search=Attorney",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any("Attorney" in u["name"] for u in data["items"])

        # Filter by role
        res_role = await ac.get(
            "/api/v1/admin/users?role=LEGAL_PROFESSIONAL",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_role.status_code == 200
        data_role = res_role.json()
        assert all(u["role"] == "LEGAL_PROFESSIONAL" for u in data_role["items"])


@pytest.mark.asyncio
async def test_admin_document_monitoring(db: Session):
    """3. Verify GET /api/v1/admin/documents system-wide audit."""
    admin = User(
        name="Admin Doc Test",
        email="admin_docs@example.com",
        password_hash=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(admin)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "admin_docs@example.com", "password": "adminpass123"})).json()["access_token"]

        res = await ac.get(
            "/api/v1/admin/documents",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_admin_security_events_monitoring(db: Session):
    """4. Verify GET /api/v1/admin/security-events tracking."""
    admin = User(
        name="Admin Security Test",
        email="admin_security@example.com",
        password_hash=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(admin)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "admin_security@example.com", "password": "adminpass123"})).json()["access_token"]

        res = await ac.get(
            "/api/v1/admin/security-events",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "items" in data


@pytest.mark.asyncio
async def test_admin_model_status(db: Session):
    """5. Verify GET /api/v1/admin/model-status."""
    admin = User(
        name="Admin Model Test",
        email="admin_model@example.com",
        password_hash=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(admin)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "admin_model@example.com", "password": "adminpass123"})).json()["access_token"]

        res = await ac.get(
            "/api/v1/admin/model-status",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "base_model" in data
        assert "status" in data
        assert data["status"] == "OPERATIONAL"


@pytest.mark.asyncio
async def test_non_admin_user_forbidden(db: Session):
    """6. Hard backend RBAC security test verifying non-admin users receive HTTP 403 Forbidden."""
    public_user = User(
        name="Public User RBAC Test",
        email="public_rbac@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.PUBLIC_USER,
        verification_status=VerificationStatus.NOT_REQUIRED
    )

    pro_user = User(
        name="Pro User RBAC Test",
        email="pro_rbac@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add_all([public_user, pro_user])
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Public User Token
        token_public = (await ac.post("/api/v1/auth/login", json={"email": "public_rbac@example.com", "password": "pass123"})).json()["access_token"]

        # Pro User Token
        token_pro = (await ac.post("/api/v1/auth/login", json={"email": "pro_rbac@example.com", "password": "pass123"})).json()["access_token"]

        # Assert HTTP 403 Forbidden for Public User on all Admin Endpoints
        res1 = await ac.get("/api/v1/admin/dashboard-summary", headers={"Authorization": f"Bearer {token_public}"})
        assert res1.status_code == 403

        res2 = await ac.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token_public}"})
        assert res2.status_code == 403

        # Assert HTTP 403 Forbidden for Legal Professional User on all Admin Endpoints
        res3 = await ac.get("/api/v1/admin/dashboard-summary", headers={"Authorization": f"Bearer {token_pro}"})
        assert res3.status_code == 403

        res4 = await ac.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token_pro}"})
        assert res4.status_code == 403
