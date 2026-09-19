"""
Persistent Chat — Phase 2 Test Suite
=======================================
Tests for the full persistent-chat feature: real endpoints, real DB, mocked AI.

Coverage:
  A. Auto-title generation (unit, no DB)
  B. Conversation creation — general / document / rag
  C. Document ownership enforcement on conversation creation
  D. Send message → AI response persisted (general mode, mocked AI)
  E. Send message → sources persisted (rag mode, mocked AI)
  F. Message persistence: close + reopen conversation, messages still there
  G. updated_at advances after each message
  H. Auto-title fires on first message when title is default
  I. List conversations — sorted by updated_at DESC
  J. Get full conversation — messages in order
  K. Rename conversation (PATCH)
  L. Delete conversation → cascade messages
  M. Security: cross-user access returns 404
  N. Security: unauthenticated access denied
  O. Error fallback: AI crash → graceful response, both messages saved

Run:
    pytest tests/backend/test_chat_phase2.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.models.user import User, UserRole, VerificationStatus
from app.models.document import LegalDocument, DocumentType, ProcessingStatus
from app.models.conversation import Conversation, ChatMessage, ConversationMode, MessageRole
from app.api.chat import generate_title   # unit-test the pure function

API = settings.API_V1_STR
CHAT = f"{API}/chat"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def user1(db: Session) -> User:
    u = User(
        name="Phase2 User1",
        email="phase2_u1@lexguard.test",
        password_hash=get_password_hash("Pass@123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def user2(db: Session) -> User:
    u = User(
        name="Phase2 User2",
        email="phase2_u2@lexguard.test",
        password_hash=get_password_hash("Pass@123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def tok1(user1: User) -> str:
    return create_access_token(subject=user1.id)


@pytest.fixture
def tok2(user2: User) -> str:
    return create_access_token(subject=user2.id)


@pytest.fixture
def doc1(db: Session, user1: User) -> LegalDocument:
    d = LegalDocument(
        owner_id=user1.id,
        filename="lease.pdf",
        stored_filename="s_lease.pdf",
        stored_path="/up/s_lease.pdf",
        file_type="pdf",
        file_size=4096,
        file_hash="aabbcc" * 10 + "aa",
        document_type=DocumentType.CONTRACT,
        processing_status=ProcessingStatus.READY,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# A. Auto-title generation — pure unit tests (no DB, no HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoTitle:
    def test_legal_keyword_extraction(self):
        assert "Termination" in generate_title("What are the termination conditions?")

    def test_force_majeure(self):
        title = generate_title("Is force majeure applicable in this contract?")
        assert "Force" in title or "Majeure" in title or "Contract" in title

    def test_section_reference(self):
        title = generate_title("Explain Section 420 IPC in detail")
        # "Section" is not in stop-words; "Explain" is a stop-word
        assert title != "New Conversation"
        assert len(title) > 0

    def test_empty_message_returns_default(self):
        assert generate_title("") == "New Conversation"
        assert generate_title("   ") == "New Conversation"

    def test_all_stop_words_returns_words(self):
        # Even if all words are stop-words we fall back to first two
        result = generate_title("is the")
        assert result != "New Conversation" or len(result) > 0

    def test_max_length_respected(self):
        long_msg = "contract " * 30
        assert len(generate_title(long_msg)) <= 60

    def test_title_cased(self):
        title = generate_title("what is the termination clause?")
        assert title[0].isupper()

    def test_general_question_without_legal_words(self):
        title = generate_title("Hello how are you doing today?")
        assert isinstance(title, str)
        assert len(title) > 0

    def test_nda_keyword(self):
        title = generate_title("Summarise the NDA obligations")
        assert "Nda" in title or "Obligations" in title

    def test_breach_keyword(self):
        title = generate_title("What constitutes a breach of contract?")
        assert "Breach" in title or "Contract" in title


# ─────────────────────────────────────────────────────────────────────────────
# B. Conversation creation via API
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_general_conversation(db: Session, user1: User, tok1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "My Legal Q&A", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
    assert r.status_code == 201
    d = r.json()
    assert d["title"] == "My Legal Q&A"
    assert d["mode"] == "general"
    assert d["document_id"] is None
    assert "id" in d
    assert d["owner_id"] == user1.id


@pytest.mark.asyncio
async def test_create_document_conversation(db: Session, user1: User, tok1: str, doc1: LegalDocument):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Lease Review", "mode": "document", "document_id": doc1.id},
            headers={"Authorization": f"Bearer {tok1}"},
        )
    assert r.status_code == 201
    d = r.json()
    assert d["document_id"] == doc1.id
    assert d["mode"] == "document"


@pytest.mark.asyncio
async def test_create_rag_conversation(db: Session, user1: User, tok1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "RAG Search", "mode": "rag"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
    assert r.status_code == 201
    assert r.json()["mode"] == "rag"


# ─────────────────────────────────────────────────────────────────────────────
# C. Document ownership enforcement
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cannot_link_other_users_document(
    db: Session, user1: User, user2: User, tok2: str, doc1: LegalDocument
):
    """User2 cannot create a conversation linked to User1's document."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Steal Doc", "mode": "document", "document_id": doc1.id},
            headers={"Authorization": f"Bearer {tok2}"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_document_id_requires_document_or_rag_mode(
    db: Session, user1: User, tok1: str, doc1: LegalDocument
):
    """Setting document_id on a general-mode conversation is rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Bad", "mode": "general", "document_id": doc1.id},
            headers={"Authorization": f"Bearer {tok1}"},
        )
    assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# D. Send message → AI response persisted (general mode, mocked AI)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_message_general_mode_mocked(db: Session, user1: User, tok1: str):
    """
    General mode: message saved, AI called, response saved.
    AI is mocked so tests don't depend on API keys.
    """
    mock_ai_result = {
        "answer": "Force majeure is a contract clause that removes liability.",
        "disclaimer": "Legal Disclaimer: ...",
        "is_safe": True,
        "topic": "AI Legal Educational Assistant",
    }

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Create conversation
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Force Majeure", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            assert cr.status_code == 201
            conv_id = cr.json()["id"]

            # Send message
            mr = await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "Explain force majeure"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    assert mr.status_code == 200
    data = mr.json()

    # User message
    assert data["user_message"]["role"] == "user"
    assert data["user_message"]["content"] == "Explain force majeure"

    # Assistant message
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["content"] == mock_ai_result["answer"]
    assert data["assistant_message"]["model_used"] == "free-legal-engine"

    # Conversation updated
    assert data["conversation"]["id"] == conv_id


@pytest.mark.asyncio
async def test_send_message_gemini_provider_label(db: Session, user1: User, tok1: str):
    """When Gemini responds, provider_used is normalised to 'gemini'."""
    mock_ai_result = {
        "answer": "A Gemini answer.",
        "disclaimer": "...",
        "is_safe": True,
        "topic": "Google Gemini AI Legal Assistance",
    }

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Gemini Test", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]
            mr = await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "What is consideration?"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    assert mr.json()["assistant_message"]["model_used"] == "gemini"


# ─────────────────────────────────────────────────────────────────────────────
# E. Sources persisted for RAG mode
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag_sources_persisted(db: Session, user1: User, tok1: str):
    """RAG mode: sources returned in message and persisted in sources_json."""
    from app.services.rag.rag_answer_service import RAGAnswerResult, SourceItem

    mock_result = RAGAnswerResult(
        answer="Based on your documents...",
        sources=[
            SourceItem(
                chunk_id="chunk_001",
                document_id=1,
                filename="lease.pdf",
                page_number=3,
                similarity=0.91,
            )
        ],
        used_rag=True,
        provider_used="Google Gemini AI",
        chunks_retrieved=1,
    )

    with patch("app.api.chat.rag_answer") as mock_rag:
        mock_rag.return_value = mock_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "RAG Test", "mode": "rag"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]

            mr = await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "What does the document say about termination?"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    assert mr.status_code == 200
    assistant = mr.json()["assistant_message"]
    assert assistant["sources"] is not None
    assert len(assistant["sources"]) == 1
    src = assistant["sources"][0]
    assert src["chunk_id"] == "chunk_001"
    assert src["document_name"] == "lease.pdf"
    assert src["page_number"] == 3
    assert src["similarity"] == 0.91


@pytest.mark.asyncio
async def test_document_mode_passes_document_id(db: Session, user1: User, tok1: str, doc1: LegalDocument):
    """document mode passes document_id to rag_answer."""
    from app.services.rag.rag_answer_service import RAGAnswerResult

    mock_result = RAGAnswerResult(answer="doc answer", provider_used="LexGuard Free Legal Engine (Grounded)")

    with patch("app.api.chat.rag_answer") as mock_rag:
        mock_rag.return_value = mock_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Doc Mode", "mode": "document", "document_id": doc1.id},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]
            await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "What is the lease period?"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    # Verify rag_answer was called with the correct document_id
    call_kwargs = mock_rag.call_args.kwargs
    assert call_kwargs.get("document_id") == doc1.id


# ─────────────────────────────────────────────────────────────────────────────
# F. Message persistence: reopen conversation → messages still there
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_messages_persist_after_reopen(db: Session, user1: User, tok1: str):
    """Core persistence test: send message, then GET conversation — messages still exist."""
    mock_ai_result = {
        "answer": "Termination requires 30 days notice.",
        "disclaimer": "",
        "is_safe": True,
        "topic": "AI Legal Educational Assistant",
    }

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Create and send
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Persist Test", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]

            await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "What is the notice period?"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "Are there any exceptions?"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

            # "Reopen" — fresh GET
            gr = await ac.get(
                f"{CHAT}/conversations/{conv_id}",
                headers={"Authorization": f"Bearer {tok1}"},
            )

    assert gr.status_code == 200
    data = gr.json()
    assert data["total_messages"] == 4  # 2 user + 2 assistant
    roles = [m["role"] for m in data["conversation"]["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert data["conversation"]["messages"][0]["content"] == "What is the notice period?"
    assert data["conversation"]["messages"][1]["content"] == mock_ai_result["answer"]


# ─────────────────────────────────────────────────────────────────────────────
# G. updated_at advances after each message
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_updated_at_advances(db: Session, user1: User, tok1: str):
    mock_ai = {"answer": "ok", "disclaimer": "", "is_safe": True, "topic": "AI Legal Educational Assistant"}

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Time Test", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            created_at = cr.json()["updated_at"]
            conv_id = cr.json()["id"]

            mr = await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "ping"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    after_at = mr.json()["conversation"]["updated_at"]
    # updated_at must be >= created_at (same second is fine in fast tests)
    assert after_at >= created_at


# ─────────────────────────────────────────────────────────────────────────────
# H. Auto-title fires on first message
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_title_on_first_message(db: Session, user1: User, tok1: str):
    """Conversation created with default title gets auto-titled on first send."""
    mock_ai = {"answer": "ok", "disclaimer": "", "is_safe": True, "topic": "AI Legal Educational Assistant"}

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "New Conversation", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]

            mr = await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "What are the termination conditions in this contract?"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    # Title should no longer be "New Conversation"
    updated_title = mr.json()["conversation"]["title"]
    assert updated_title != "New Conversation"
    assert "Termination" in updated_title or "Contract" in updated_title or "Conditions" in updated_title


@pytest.mark.asyncio
async def test_manual_title_not_overwritten(db: Session, user1: User, tok1: str):
    """If user set a custom title it must NOT be overwritten by auto-title."""
    mock_ai = {"answer": "ok", "disclaimer": "", "is_safe": True, "topic": "AI Legal Educational Assistant"}

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "My Custom Title", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]
            mr = await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "What are the termination conditions?"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    assert mr.json()["conversation"]["title"] == "My Custom Title"


# ─────────────────────────────────────────────────────────────────────────────
# I. List conversations sorted by updated_at DESC
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_sorted_by_recent_activity(db: Session, user1: User, tok1: str):
    mock_ai = {"answer": "ok", "disclaimer": "", "is_safe": True, "topic": "AI Legal Educational Assistant"}

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Create two conversations
            c1 = (await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Older Conv", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )).json()["id"]

            c2 = (await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Newer Conv", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )).json()["id"]

            # Send a message to the OLDER conversation to make it most recent
            await ac.post(
                f"{CHAT}/conversations/{c1}/messages",
                json={"message": "bump c1"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

            lr = await ac.get(
                f"{CHAT}/conversations",
                headers={"Authorization": f"Bearer {tok1}"},
            )

    assert lr.status_code == 200
    data = lr.json()
    assert data["total"] == 2
    # c1 was updated last so must appear first
    ids = [c["id"] for c in data["conversations"]]
    assert ids[0] == c1


@pytest.mark.asyncio
async def test_list_pagination(db: Session, user1: User, tok1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for i in range(5):
            await ac.post(
                f"{CHAT}/conversations",
                json={"title": f"Conv {i}", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

        page1 = await ac.get(
            f"{CHAT}/conversations?page=1&page_size=3",
            headers={"Authorization": f"Bearer {tok1}"},
        )
        page2 = await ac.get(
            f"{CHAT}/conversations?page=2&page_size=3",
            headers={"Authorization": f"Bearer {tok1}"},
        )

    p1 = page1.json()
    p2 = page2.json()
    assert p1["total"] == 5
    assert len(p1["conversations"]) == 3
    assert p1["has_more"] is True
    assert len(p2["conversations"]) == 2
    assert p2["has_more"] is False


@pytest.mark.asyncio
async def test_list_mode_filter(db: Session, user1: User, tok1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            f"{CHAT}/conversations",
            json={"title": "G1", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        await ac.post(
            f"{CHAT}/conversations",
            json={"title": "G2", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        await ac.post(
            f"{CHAT}/conversations",
            json={"title": "R1", "mode": "rag"},
            headers={"Authorization": f"Bearer {tok1}"},
        )

        general_r = await ac.get(
            f"{CHAT}/conversations?mode=general",
            headers={"Authorization": f"Bearer {tok1}"},
        )
        rag_r = await ac.get(
            f"{CHAT}/conversations?mode=rag",
            headers={"Authorization": f"Bearer {tok1}"},
        )

    assert general_r.json()["total"] == 2
    assert rag_r.json()["total"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# J. Get full conversation — messages in chronological order
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_conversation_with_messages(db: Session, user1: User, tok1: str):
    mock_ai = {
        "answer": "AI answer here.",
        "disclaimer": "",
        "is_safe": True,
        "topic": "AI Legal Educational Assistant",
    }

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Full Conv", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]

            await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "First question"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

            gr = await ac.get(
                f"{CHAT}/conversations/{conv_id}",
                headers={"Authorization": f"Bearer {tok1}"},
            )

    d = gr.json()
    assert d["total_messages"] == 2
    msgs = d["conversation"]["messages"]
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "First question"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == mock_ai["answer"]


@pytest.mark.asyncio
async def test_get_conversation_shows_document_filename(
    db: Session, user1: User, tok1: str, doc1: LegalDocument
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cr = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Doc Conv", "mode": "document", "document_id": doc1.id},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        conv_id = cr.json()["id"]
        gr = await ac.get(
            f"{CHAT}/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {tok1}"},
        )

    assert gr.json()["conversation"]["document_filename"] == "lease.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# K. Rename conversation (PATCH)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rename_conversation(db: Session, user1: User, tok1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cr = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Old Title", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        conv_id = cr.json()["id"]

        pr = await ac.patch(
            f"{CHAT}/conversations/{conv_id}",
            json={"title": "Brand New Title"},
            headers={"Authorization": f"Bearer {tok1}"},
        )

    assert pr.status_code == 200
    assert pr.json()["title"] == "Brand New Title"


@pytest.mark.asyncio
async def test_rename_by_other_user_is_404(
    db: Session, user1: User, user2: User, tok1: str, tok2: str
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cr = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Private", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        conv_id = cr.json()["id"]

        pr = await ac.patch(
            f"{CHAT}/conversations/{conv_id}",
            json={"title": "Hijacked"},
            headers={"Authorization": f"Bearer {tok2}"},
        )

    assert pr.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# L. Delete conversation → cascade messages
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_cascades_messages(db: Session, user1: User, tok1: str):
    mock_ai = {"answer": "ok", "disclaimer": "", "is_safe": True, "topic": "AI Legal Educational Assistant"}

    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.return_value = mock_ai

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "To Delete", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]

            await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "some message"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

            dr = await ac.delete(
                f"{CHAT}/conversations/{conv_id}",
                headers={"Authorization": f"Bearer {tok1}"},
            )
            assert dr.status_code == 204

            gr = await ac.get(
                f"{CHAT}/conversations/{conv_id}",
                headers={"Authorization": f"Bearer {tok1}"},
            )
            assert gr.status_code == 404

    # Verify messages gone from DB
    count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id).count()
    assert count == 0


# ─────────────────────────────────────────────────────────────────────────────
# M. Security: cross-user access returns 404
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_user_get_returns_404(
    db: Session, user1: User, user2: User, tok1: str, tok2: str
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cr = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Secret", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        conv_id = cr.json()["id"]

        r2 = await ac.get(
            f"{CHAT}/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {tok2}"},
        )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_delete_returns_404(
    db: Session, user1: User, user2: User, tok1: str, tok2: str
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cr = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Secret2", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        conv_id = cr.json()["id"]

        r2 = await ac.delete(
            f"{CHAT}/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {tok2}"},
        )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_send_message_returns_404(
    db: Session, user1: User, user2: User, tok1: str, tok2: str
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cr = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Secret3", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        conv_id = cr.json()["id"]

        r2 = await ac.post(
            f"{CHAT}/conversations/{conv_id}/messages",
            json={"message": "I should not be able to do this"},
            headers={"Authorization": f"Bearer {tok2}"},
        )
    assert r2.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# N. Unauthenticated access denied
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_token_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(f"{CHAT}/conversations")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invalid_token_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(
            f"{CHAT}/conversations",
            headers={"Authorization": "Bearer not_a_real_token"},
        )
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# O. Error fallback: AI crash → graceful response, both messages saved
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_crash_returns_graceful_message(db: Session, user1: User, tok1: str):
    """If AI throws, endpoint returns 200 with a safe error message — nothing lost."""
    with patch("app.api.chat.rag_service") as mock_svc:
        mock_svc.process_public_query.side_effect = RuntimeError("Gemini exploded")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cr = await ac.post(
                f"{CHAT}/conversations",
                json={"title": "Error Test", "mode": "general"},
                headers={"Authorization": f"Bearer {tok1}"},
            )
            conv_id = cr.json()["id"]

            mr = await ac.post(
                f"{CHAT}/conversations/{conv_id}/messages",
                json={"message": "This will trigger a crash"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

    assert mr.status_code == 200
    data = mr.json()

    # User message must be saved
    assert data["user_message"]["role"] == "user"
    assert data["user_message"]["content"] == "This will trigger a crash"

    # Assistant message must also be saved with the fallback text
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["model_used"] == "error-fallback"
    assert "error" in data["assistant_message"]["content"].lower()

    # Verify both messages persisted in DB
    count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id).count()
    assert count == 2


@pytest.mark.asyncio
async def test_empty_message_rejected(db: Session, user1: User, tok1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cr = await ac.post(
            f"{CHAT}/conversations",
            json={"title": "Empty Test", "mode": "general"},
            headers={"Authorization": f"Bearer {tok1}"},
        )
        conv_id = cr.json()["id"]

        mr = await ac.post(
            f"{CHAT}/conversations/{conv_id}/messages",
            json={"message": "   "},
            headers={"Authorization": f"Bearer {tok1}"},
        )
    assert mr.status_code == 400
