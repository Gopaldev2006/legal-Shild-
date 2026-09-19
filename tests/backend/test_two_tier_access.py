import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User, UserRole, VerificationStatus
from app.models.document import LegalDocument, DocumentChunk, ProcessingStatus, DocumentType
from app.core.security import get_password_hash
from app.services.vector.vector_repository import vector_repo
from app.services.vector.indexing_service import index_document_chunks


@pytest.fixture(autouse=True)
def clear_vector_store():
    vector_repo.clear_all()
    yield
    vector_repo.clear_all()


@pytest.mark.asyncio
async def test_public_user_can_access_public_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/rag/public-query",
            json={"query": "What is habeas corpus?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "General Legal Explanation" in data["answer"] or "habeas corpus" in data["answer"].lower()
        assert "Legal Disclaimer:" in data["disclaimer"]
        assert data["is_safe"] is True


@pytest.mark.asyncio
async def test_public_query_returns_disclaimer_and_no_documents():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/rag/public-query",
            json={"query": "Explain section 302 IPC penalties"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "Legal Disclaimer:" in data["disclaimer"]
        # Public endpoint output structure has no citations key
        assert "citations" not in data


@pytest.mark.asyncio
async def test_public_user_cannot_access_professional_rag(db):
    user = User(
        name="John Public",
        email="john_pub@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.PUBLIC_USER,
        verification_status=VerificationStatus.NOT_REQUIRED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "john_pub@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.post(
            "/api/v1/rag/query",
            json={"query": "Analyze case documents"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 403
        assert "Permission denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_unverified_professional_cannot_access_professional_rag(db):
    user = User(
        name="Unverified Lawyer",
        email="lawyer_pending@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.PENDING
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "lawyer_pending@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.post(
            "/api/v1/rag/query",
            json={"query": "Analyze case documents"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 403
        assert "Verification" in res.json()["detail"] or "Permission denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_unverified_professional_cannot_access_audit_history(db):
    user = User(
        name="Rejected Lawyer",
        email="lawyer_rej@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.REJECTED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "lawyer_rej@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.get(
            "/api/v1/rag/audit-history",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 403


@pytest.mark.asyncio
async def test_verified_professional_can_access_rag_and_audit_history(db):
    user = User(
        name="Adv. Verified Pro",
        email="pro_verified@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "pro_verified@example.com", "password": "pass123"})).json()["access_token"]

        # 1. Execute RAG Query
        rag_res = await ac.post(
            "/api/v1/rag/query",
            json={"query": "What are arbitration rules under Section 11?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert rag_res.status_code == 200

        # 2. Query Audit History
        audit_res = await ac.get(
            "/api/v1/rag/audit-history",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert audit_res.status_code == 200
        logs = audit_res.json()
        assert len(logs) == 1
        assert logs[0]["user_id"] == user.id
        assert "arbitration" in logs[0]["query_text"].lower()


@pytest.mark.asyncio
async def test_verified_professional_can_extract_arguments(db):
    user = User(
        name="Adv. Extraction Pro",
        email="extract_pro@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    doc = LegalDocument(
        owner_id=user.id,
        filename="court_brief.txt",
        stored_filename="u_ext.txt",
        stored_path="/tmp/u_ext.txt",
        file_type="txt",
        file_size=150,
        file_hash="hash_ext_1",
        document_type=DocumentType.CASE_BRIEF,
        processing_status=ProcessingStatus.COMPLETED
    )
    db.add(doc)
    db.commit()

    chk = DocumentChunk(
        chunk_id="chk_ext_1",
        document_id=doc.id,
        owner_id=user.id,
        text="The petitioner contends breach under Section 302 and Article 21 rights violation.",
        page_number=1,
        chunk_index=0
    )
    db.add(chk)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "extract_pro@example.com", "password": "pass123"})).json()["access_token"]

        ext_res = await ac.post(
            f"/api/v1/rag/extract-arguments/{doc.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert ext_res.status_code == 200
        data = ext_res.json()
        assert data["document_id"] == doc.id
        assert data["filename"] == "court_brief.txt"
        assert len(data["cited_statutes"]) > 0
        assert len(data["key_arguments"]) > 0
