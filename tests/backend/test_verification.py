import io
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User, UserRole, VerificationStatus
from app.models.verification import VerificationRequest
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_unauthorized_verification_access():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        status_resp = await ac.get("/api/v1/verification/status")
        assert status_resp.status_code in (401, 403)

        admin_resp = await ac.get("/api/v1/admin/verifications")
        assert admin_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_upload_file_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/register", json={"name": "User One", "email": "user1@example.com", "password": "Password123!"})
        login_resp = await ac.post("/api/v1/auth/login", json={"email": "user1@example.com", "password": "Password123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Invalid file extension (.exe)
        bad_file = ("script.exe", io.BytesIO(b"malicious_code"), "application/x-msdownload")
        resp1 = await ac.post("/api/v1/verification/request", files={"file": bad_file}, headers=headers)
        assert resp1.status_code == 400
        assert "Invalid file type" in resp1.json()["detail"]

        # 2. Valid file (.pdf)
        good_file = ("certificate.pdf", io.BytesIO(b"%PDF-1.4 Bar Council Certificate Content"), "application/pdf")
        resp2 = await ac.post("/api/v1/verification/request", files={"file": good_file}, headers=headers)
        assert resp2.status_code == 201
        data = resp2.json()
        assert data["status"] == VerificationStatus.PENDING.value
        assert "document_hash" in data


@pytest.mark.asyncio
async def test_normal_user_cannot_approve(db):
    public_user = User(name="Public User", email="pub@example.com", password_hash=get_password_hash("pass123"), role=UserRole.PUBLIC_USER)
    db.add(public_user)
    db.commit()
    
    req = VerificationRequest(user_id=public_user.id, document_path="/tmp/doc.pdf", document_hash="hash123", status=VerificationStatus.PENDING)
    db.add(req)
    db.commit()
    req_id = req.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "pub@example.com", "password": "pass123"})).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        approve_resp = await ac.post(f"/api/v1/admin/verifications/{req_id}/approve", headers=headers)
        assert approve_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_approve(db):
    applicant = User(name="Adv. Sharma", email="sharma@example.com", password_hash=get_password_hash("pass123"), role=UserRole.PUBLIC_USER, verification_status=VerificationStatus.NOT_REQUIRED)
    admin = User(name="Admin User", email="admin@example.com", password_hash=get_password_hash("pass123"), role=UserRole.ADMIN)
    db.add_all([applicant, admin])
    db.commit()

    req = VerificationRequest(user_id=applicant.id, document_path="/tmp/doc.pdf", document_hash="hash123", status=VerificationStatus.PENDING)
    db.add(req)
    db.commit()
    req_id = req.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        admin_token = (await ac.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "pass123"})).json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        approve_resp = await ac.post(
            f"/api/v1/admin/verifications/{req_id}/approve",
            json={"review_notes": "Bar Council License Verified"},
            headers=headers
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["new_role"] == UserRole.LEGAL_PROFESSIONAL.value
        assert approve_resp.json()["verification_status"] == VerificationStatus.VERIFIED.value

    updated_user = db.query(User).filter(User.email == "sharma@example.com").first()
    assert updated_user.role == UserRole.LEGAL_PROFESSIONAL
    assert updated_user.verification_status == VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_unverified_user_cannot_access_professional_apis():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/register", json={"name": "Public User", "email": "pub2@example.com", "password": "Password123!"})
        token = (await ac.post("/api/v1/auth/login", json={"email": "pub2@example.com", "password": "Password123!"})).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        pro_resp = await ac.get("/api/v1/auth/professional-only", headers=headers)
        assert pro_resp.status_code == 403


@pytest.mark.asyncio
async def test_verified_user_can_access_professional_apis(db):
    verified_user = User(
        name="Adv. Verma",
        email="verma@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(verified_user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "verma@example.com", "password": "pass123"})).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        pro_resp = await ac.get("/api/v1/auth/professional-only", headers=headers)
        assert pro_resp.status_code == 200
        assert pro_resp.json()["role"] == "LEGAL_PROFESSIONAL"
