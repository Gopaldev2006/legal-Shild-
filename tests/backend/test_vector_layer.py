import io
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User, UserRole, VerificationStatus
from app.models.document import LegalDocument, DocumentChunk, ProcessingStatus, DocumentType
from app.core.security import get_password_hash
from app.services.vector.embedding_service import generate_embedding, generate_embeddings_batch
from app.services.vector.vector_repository import vector_repo
from app.services.vector.indexing_service import index_document_chunks
from app.services.vector.retrieval_service import retrieval_service, UserContext


@pytest.fixture(autouse=True)
def clear_vector_store():
    vector_repo.clear_all()
    yield
    vector_repo.clear_all()


def test_embedding_generation():
    text = "Section 302 Indian Penal Code Murder and Culpable Homicide"
    vec = generate_embedding(text)
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert isinstance(vec[0], float)

    batch_vecs = generate_embeddings_batch(["Text one", "Text two"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 384


def test_vector_indexing(db):
    user = User(name="Adv. Index", email="index@example.com", password_hash=get_password_hash("pass123"), role=UserRole.LEGAL_PROFESSIONAL, verification_status=VerificationStatus.VERIFIED)
    db.add(user)
    db.commit()

    doc = LegalDocument(
        owner_id=user.id,
        filename="index_test.txt",
        stored_filename="uuid.txt",
        stored_path="/tmp/uuid.txt",
        file_type="txt",
        file_size=100,
        file_hash="hash123",
        document_type=DocumentType.CASE_BRIEF,
        processing_status=ProcessingStatus.COMPLETED
    )
    db.add(doc)
    db.commit()

    chk = DocumentChunk(
        chunk_id="chk_test_1",
        document_id=doc.id,
        owner_id=user.id,
        text="Constitutional Law Fundamental Rights Article 21 Right to Life",
        page_number=1,
        chunk_index=0
    )
    db.add(chk)
    db.commit()

    count = index_document_chunks(db, doc.id)
    assert count == 1
    assert len(vector_repo.metadata_store) == 1
    assert vector_repo.metadata_store[0]["document_id"] == doc.id


def test_vector_search(db):
    user = User(name="Adv. Search", email="search@example.com", password_hash=get_password_hash("pass123"), role=UserRole.LEGAL_PROFESSIONAL, verification_status=VerificationStatus.VERIFIED)
    db.add(user)
    db.commit()

    doc = LegalDocument(
        owner_id=user.id,
        filename="search_doc.txt",
        stored_filename="uuid2.txt",
        stored_path="/tmp/uuid2.txt",
        file_type="txt",
        file_size=120,
        file_hash="hash456",
        document_type=DocumentType.COURT_ORDER,
        processing_status=ProcessingStatus.COMPLETED
    )
    db.add(doc)
    db.commit()

    chk = DocumentChunk(
        chunk_id="chk_search_1",
        document_id=doc.id,
        owner_id=user.id,
        text="Arbitration and Conciliation Act Section 11 Appointment of Arbitrator",
        page_number=1,
        chunk_index=0
    )
    db.add(chk)
    db.commit()

    index_document_chunks(db, doc.id)

    user_ctx = UserContext(user_id=user.id, role="LEGAL_PROFESSIONAL")
    results = retrieval_service.search("Arbitrator Appointment Guidelines", user_context=user_ctx, top_k=5)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chk_search_1"
    assert "Arbitration" in results[0]["text"]


def test_metadata_filtering(db):
    user = User(name="Adv. Filter", email="filter@example.com", password_hash=get_password_hash("pass123"), role=UserRole.LEGAL_PROFESSIONAL, verification_status=VerificationStatus.VERIFIED)
    db.add(user)
    db.commit()

    doc1 = LegalDocument(owner_id=user.id, filename="doc1.txt", stored_filename="u1.txt", stored_path="/tmp/u1.txt", file_type="txt", file_size=10, file_hash="h1", document_type=DocumentType.CONTRACT, matter_id="MAT-101", processing_status=ProcessingStatus.COMPLETED)
    doc2 = LegalDocument(owner_id=user.id, filename="doc2.txt", stored_filename="u2.txt", stored_path="/tmp/u2.txt", file_type="txt", file_size=10, file_hash="h2", document_type=DocumentType.STATUTE, matter_id="MAT-202", processing_status=ProcessingStatus.COMPLETED)
    db.add_all([doc1, doc2])
    db.commit()

    chk1 = DocumentChunk(chunk_id="chk_mat_101", document_id=doc1.id, owner_id=user.id, matter_id="MAT-101", text="Contract Liability Clause for Matter 101", chunk_index=0)
    chk2 = DocumentChunk(chunk_id="chk_mat_202", document_id=doc2.id, owner_id=user.id, matter_id="MAT-202", text="Statutory Environmental Protection Law 2026", chunk_index=0)
    db.add_all([chk1, chk2])
    db.commit()

    index_document_chunks(db, doc1.id)
    index_document_chunks(db, doc2.id)

    user_ctx = UserContext(user_id=user.id, role="LEGAL_PROFESSIONAL")
    results = retrieval_service.search("Environmental Protection", user_context=user_ctx, filters={"matter_id": "MAT-202"})

    assert len(results) == 1
    assert results[0]["matter_id"] == "MAT-202"
    assert "Environmental" in results[0]["text"]


@pytest.mark.asyncio
async def test_unauthorized_document_exclusion(db):
    # Setup User A and User B
    user_a = User(name="Attorney A", email="attorney_a@example.com", password_hash=get_password_hash("pass123"), role=UserRole.LEGAL_PROFESSIONAL, verification_status=VerificationStatus.VERIFIED)
    user_b = User(name="Attorney B", email="attorney_b@example.com", password_hash=get_password_hash("pass123"), role=UserRole.LEGAL_PROFESSIONAL, verification_status=VerificationStatus.VERIFIED)
    db.add_all([user_a, user_b])
    db.commit()

    # User A uploads & indexes highly confidential document
    doc_a = LegalDocument(owner_id=user_a.id, filename="confidential_a.txt", stored_filename="ua.txt", stored_path="/tmp/ua.txt", file_type="txt", file_size=10, file_hash="ha", document_type=DocumentType.CONTRACT, processing_status=ProcessingStatus.COMPLETED)
    db.add(doc_a)
    db.commit()

    chk_a = DocumentChunk(chunk_id="chk_sec_a", document_id=doc_a.id, owner_id=user_a.id, text="Highly Secret Patent Settlement Agreement between Corporation Alpha and Corporation Beta", chunk_index=0)
    db.add(chk_a)
    db.commit()

    index_document_chunks(db, doc_a.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token_a = (await ac.post("/api/v1/auth/login", json={"email": "attorney_a@example.com", "password": "pass123"})).json()["access_token"]
        token_b = (await ac.post("/api/v1/auth/login", json={"email": "attorney_b@example.com", "password": "pass123"})).json()["access_token"]

        # 1. User B searches for exact query matching User A's confidential vector
        res_b = await ac.post(
            "/api/v1/vector/search",
            json={"query": "Patent Settlement Agreement Corporation Alpha", "top_k": 5},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_b.status_code == 200
        # CRUCIAL SECURITY CHECK: User B receives ZERO results because owner_id != user_b.id
        assert res_b.json()["results_count"] == 0

        # 2. User A searches the exact same query -> User A receives 1 matching result
        res_a = await ac.post(
            "/api/v1/vector/search",
            json={"query": "Patent Settlement Agreement Corporation Alpha", "top_k": 5},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_a.status_code == 200
        assert res_a.json()["results_count"] == 1
        assert res_a.json()["results"][0]["chunk_id"] == "chk_sec_a"
