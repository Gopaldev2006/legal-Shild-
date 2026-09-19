import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User, UserRole, VerificationStatus
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_successful_registration():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Jane Citizen",
                "email": "jane@example.com",
                "password": "SecretPassword123!"
            }
        )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "jane@example.com"
    assert data["name"] == "Jane Citizen"
    assert data["role"] == UserRole.PUBLIC_USER.value
    assert data["verification_status"] == VerificationStatus.NOT_REQUIRED.value
    assert "password_hash" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_duplicate_email_registration():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Original User",
                "email": "duplicate@example.com",
                "password": "Password123!"
            }
        )
        response = await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Imposter User",
                "email": "duplicate@example.com",
                "password": "Password456!"
            }
        )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_registration_role_tampering_prevention():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Hacker User",
                "email": "hacker@example.com",
                "password": "Password123!",
                "role": "LEGAL_PROFESSIONAL",
                "verification_status": "VERIFIED"
            }
        )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == UserRole.PUBLIC_USER.value
    assert data["verification_status"] == VerificationStatus.NOT_REQUIRED.value


@pytest.mark.asyncio
async def test_successful_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "password": "MySecretPassword123"
            }
        )
        response = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "john@example.com",
                "password": "MySecretPassword123"
            }
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "john@example.com"


@pytest.mark.asyncio
async def test_incorrect_password_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "password": "CorrectPassword123"
            }
        )
        response = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "john@example.com",
                "password": "WRONGPassword123"
            }
        )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_token_access():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_garbage_token_12345"}
        )
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_protected_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        unauth_resp = await ac.get("/api/v1/auth/me")
        assert unauth_resp.status_code in (401, 403)

        await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Alice Smith",
                "email": "alice@example.com",
                "password": "Password123!"
            }
        )
        login_resp = await ac.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "Password123!"}
        )
        token = login_resp.json()["access_token"]

        auth_resp = await ac.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert auth_resp.status_code == 200
        assert auth_resp.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_role_based_authorization(db):
    public_user = User(
        name="Public User",
        email="public@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.PUBLIC_USER,
        verification_status=VerificationStatus.NOT_REQUIRED
    )
    pro_user = User(
        name="Pro Attorney",
        email="pro@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    admin_user = User(
        name="System Admin",
        email="admin@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.ADMIN,
        verification_status=VerificationStatus.NOT_REQUIRED
    )
    db.add_all([public_user, pro_user, admin_user])
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pub_token = (await ac.post("/api/v1/auth/login", json={"email": "public@example.com", "password": "pass123"})).json()["access_token"]
        pro_token = (await ac.post("/api/v1/auth/login", json={"email": "pro@example.com", "password": "pass123"})).json()["access_token"]
        admin_token = (await ac.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "pass123"})).json()["access_token"]

        pub_pro_resp = await ac.get("/api/v1/auth/professional-only", headers={"Authorization": f"Bearer {pub_token}"})
        assert pub_pro_resp.status_code == 403

        pub_admin_resp = await ac.get("/api/v1/auth/admin-only", headers={"Authorization": f"Bearer {pub_token}"})
        assert pub_admin_resp.status_code == 403

        pro_pro_resp = await ac.get("/api/v1/auth/professional-only", headers={"Authorization": f"Bearer {pro_token}"})
        assert pro_pro_resp.status_code == 200

        pro_admin_resp = await ac.get("/api/v1/auth/admin-only", headers={"Authorization": f"Bearer {pro_token}"})
        assert pro_admin_resp.status_code == 403

        admin_admin_resp = await ac.get("/api/v1/auth/admin-only", headers={"Authorization": f"Bearer {admin_token}"})
        assert admin_admin_resp.status_code == 200
