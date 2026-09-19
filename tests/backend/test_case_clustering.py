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
async def test_generate_clusters(db):
    user = User(
        name="Adv. Cluster Pro",
        email="cluster_pro@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "cluster_pro@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.post(
            "/api/v1/cases/clusters/generate",
            json={"num_clusters": 3},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["clusters_generated"] == 3
        assert data["total_cases_clustered"] > 0
        assert "AI-Assisted Semantic Grouping Notice" in data["disclaimer"]
        assert len(data["clusters"]) == 3


@pytest.mark.asyncio
async def test_get_clusters(db):
    user = User(
        name="Adv. Cluster Reader",
        email="cluster_read@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "cluster_read@example.com", "password": "pass123"})).json()["access_token"]

        # 1. Generate initial clusters
        await ac.post("/api/v1/cases/clusters/generate", json={"num_clusters": 2}, headers={"Authorization": f"Bearer {token}"})

        # 2. Get clusters list
        res = await ac.get("/api/v1/cases/clusters", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        clusters = res.json()
        assert len(clusters) == 2
        assert "representative_cases" in clusters[0]
        assert "case_count" in clusters[0]


@pytest.mark.asyncio
async def test_get_cluster_details(db):
    user = User(
        name="Adv. Cluster Detailer",
        email="cluster_det@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "cluster_det@example.com", "password": "pass123"})).json()["access_token"]

        await ac.post("/api/v1/cases/clusters/generate", json={"num_clusters": 2}, headers={"Authorization": f"Bearer {token}"})

        res = await ac.get("/api/v1/cases/clusters/0", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["cluster_id"] == 0
        assert data["case_count"] > 0
        assert len(data["cases"]) > 0
        assert "AI-Assisted Semantic Grouping Notice" in data["disclaimer"]


@pytest.mark.asyncio
async def test_unauthorized_clustering_access(db):
    pub_user = User(name="Public User", email="pub_cluster@example.com", password_hash=get_password_hash("pass123"), role=UserRole.PUBLIC_USER, verification_status=VerificationStatus.NOT_REQUIRED)
    unv_pro = User(name="Pending Lawyer", email="pending_cluster@example.com", password_hash=get_password_hash("pass123"), role=UserRole.LEGAL_PROFESSIONAL, verification_status=VerificationStatus.PENDING)
    db.add_all([pub_user, unv_pro])
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        tok_pub = (await ac.post("/api/v1/auth/login", json={"email": "pub_cluster@example.com", "password": "pass123"})).json()["access_token"]
        tok_unv = (await ac.post("/api/v1/auth/login", json={"email": "pending_cluster@example.com", "password": "pass123"})).json()["access_token"]

        res1 = await ac.post("/api/v1/cases/clusters/generate", json={"num_clusters": 3}, headers={"Authorization": f"Bearer {tok_pub}"})
        assert res1.status_code == 403

        res2 = await ac.get("/api/v1/cases/clusters", headers={"Authorization": f"Bearer {tok_unv}"})
        assert res2.status_code == 403
