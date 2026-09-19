import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User, UserRole, VerificationStatus
from app.core.security import get_password_hash
from app.services.cases.case_vector_store import case_vector_repo
from app.services.cases.case_loader import seed_public_academic_cases


@pytest.fixture(autouse=True)
def setup_cases(db):
    case_vector_repo.clear_all()
    seed_public_academic_cases(db)
    yield
    case_vector_repo.clear_all()


@pytest.mark.asyncio
async def test_similar_case_search(db):
    user = User(
        name="Adv. Case Searcher",
        email="cases_pro@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "cases_pro@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.post(
            "/api/v1/cases/search",
            json={"query": "arbitration foreign seat London agreement", "top_k": 3},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        first_case = data["results"][0]
        assert "BALCO" in first_case["title"] or "Arbitration" in first_case["title"] or "Kaiser" in first_case["title"]
        assert first_case["similarity_score"] > 0
        assert "relevant_facts" in first_case
        assert "legal_issues" in first_case
        assert "arguments" in first_case
        assert "decision" in first_case
        assert "source" in first_case


@pytest.mark.asyncio
async def test_case_metadata_filtering(db):
    user = User(
        name="Adv. Filter Pro",
        email="filter_cases@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "filter_cases@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.post(
            "/api/v1/cases/search",
            json={"query": "Basic Structure Constitution amendment", "jurisdiction": "Constitutional", "top_k": 5},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        for item in data["results"]:
            assert "Constitutional" in item["jurisdiction"]


@pytest.mark.asyncio
async def test_unauthorized_access(db):
    pub_user = User(
        name="Public Reader",
        email="pub_reader@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.PUBLIC_USER,
        verification_status=VerificationStatus.NOT_REQUIRED
    )
    unverified_pro = User(
        name="Unverified Attorney",
        email="unv_attorney@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.PENDING
    )
    db.add_all([pub_user, unverified_pro])
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token_pub = (await ac.post("/api/v1/auth/login", json={"email": "pub_reader@example.com", "password": "pass123"})).json()["access_token"]
        token_unv = (await ac.post("/api/v1/auth/login", json={"email": "unv_attorney@example.com", "password": "pass123"})).json()["access_token"]

        # 1. Public user attempt
        res1 = await ac.post(
            "/api/v1/cases/search",
            json={"query": "Any query"},
            headers={"Authorization": f"Bearer {token_pub}"}
        )
        assert res1.status_code == 403

        # 2. Unverified professional attempt
        res2 = await ac.post(
            "/api/v1/cases/search",
            json={"query": "Any query"},
            headers={"Authorization": f"Bearer {token_unv}"}
        )
        assert res2.status_code == 403

        # 3. GET case detail unauthorized attempt
        res3 = await ac.get(
            "/api/v1/cases/CASE-2024-001",
            headers={"Authorization": f"Bearer {token_pub}"}
        )
        assert res3.status_code == 403


@pytest.mark.asyncio
async def test_empty_results(db):
    user = User(
        name="Adv. Zero",
        email="zero_cases@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "zero_cases@example.com", "password": "pass123"})).json()["access_token"]

        # Search with impossible jurisdiction filter
        res = await ac.post(
            "/api/v1/cases/search",
            json={"query": "Arbitration", "jurisdiction": "NonExistentJurisdiction9999", "top_k": 5},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert len(data["results"]) == 0


@pytest.mark.asyncio
async def test_missing_field_fallback(db):
    user = User(
        name="Adv. Fallback",
        email="fallback_cases@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "fallback_cases@example.com", "password": "pass123"})).json()["access_token"]

        # 1. Fetch details for valid case
        res_valid = await ac.get(
            "/api/v1/cases/CASE-2024-001",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_valid.status_code == 200
        valid_data = res_valid.json()
        assert valid_data["case_id"] == "CASE-2024-001"
        assert valid_data["title"] != "Not available in the indexed source."

        # 2. Fetch details for non-existent case ID -> missing fields display fallback string
        res_missing = await ac.get(
            "/api/v1/cases/CASE-UNKNOWN-999",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_missing.status_code == 200
        missing_data = res_missing.json()
        assert missing_data["title"] == "Not available in the indexed source."
        assert missing_data["court"] == "Not available in the indexed source."
