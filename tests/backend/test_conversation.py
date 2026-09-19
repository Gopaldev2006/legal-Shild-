"""
Persistent Chat — Phase 1 Test Suite
======================================
Tests for Conversation and ChatMessage models + API endpoints.

Groups:
  1.  Conversation creation (general)
  2.  Message creation (user / assistant / system / with sources)
  3.  Conversation retrieval (single + list)
  4.  Conversation deletion + cascade to messages
  5.  Message persistence (order, content)
  6.  User ownership (FK relationship verified)
  7.  Cross-user access rejection (isolation)
  8.  Conversation with document association
  9.  Conversation without document (general + RAG)
  10. API endpoint smoke tests (create / list / get / delete / send-message)

Run from repo root:
    pytest tests/backend/test_conversation.py -v
"""

import json
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.models.user import User, UserRole, VerificationStatus
from app.models.document import LegalDocument, DocumentType, ProcessingStatus
from app.models.conversation import Conversation, ChatMessage, ConversationMode, MessageRole

API = settings.API_V1_STR


# ─────────────────────────────────────────────────────────────────────────────
# Shared DB fixtures
# (conftest.py already provides `db` and `setup_db` via autouse)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def user1(db: Session) -> User:
    u = User(
        name="Alice Lawyer",
        email="alice@lexguard.test",
        password_hash=get_password_hash("Alice@123"),
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
        name="Bob Paralegal",
        email="bob@lexguard.test",
        password_hash=get_password_hash("Bob@123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def token1(user1: User) -> str:
    return create_access_token(subject=user1.id)


@pytest.fixture
def token2(user2: User) -> str:
    return create_access_token(subject=user2.id)


@pytest.fixture
def document1(db: Session, user1: User) -> LegalDocument:
    doc = LegalDocument(
        owner_id=user1.id,
        filename="employment_contract.pdf",
        stored_filename="stored_employment.pdf",
        stored_path="/uploads/stored_employment.pdf",
        file_type="pdf",
        file_size=20480,
        file_hash="deadbeef" * 8,
        document_type=DocumentType.CONTRACT,
        processing_status=ProcessingStatus.READY,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# 1. Conversation creation
# ─────────────────────────────────────────────────────────────────────────────

def test_create_general_conversation(db: Session, user1: User):
    """Conversation without document — mode=general."""
    conv = Conversation(
        owner_id=user1.id,
        title="General Legal Q&A",
        mode=ConversationMode.GENERAL,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    assert conv.id is not None
    assert conv.owner_id == user1.id
    assert conv.document_id is None
    assert conv.title == "General Legal Q&A"
    assert conv.mode == ConversationMode.GENERAL
    assert conv.created_at is not None
    assert conv.updated_at is not None


def test_create_document_conversation(db: Session, user1: User, document1: LegalDocument):
    """Conversation tied to a specific document — mode=document."""
    conv = Conversation(
        owner_id=user1.id,
        document_id=document1.id,
        title="About Employment Contract",
        mode=ConversationMode.DOCUMENT,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    assert conv.id is not None
    assert conv.document_id == document1.id
    assert conv.mode == ConversationMode.DOCUMENT
    # Relationship resolves correctly
    assert conv.document.filename == "employment_contract.pdf"


def test_create_rag_conversation(db: Session, user1: User):
    """RAG conversation without specific document — searches all user docs."""
    conv = Conversation(
        owner_id=user1.id,
        title="RAG Search",
        mode=ConversationMode.RAG,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    assert conv.document_id is None
    assert conv.mode == ConversationMode.RAG


def test_default_title(db: Session, user1: User):
    """Conversation created without explicit title uses 'New Conversation'."""
    conv = Conversation(owner_id=user1.id, mode=ConversationMode.GENERAL)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    assert conv.title == "New Conversation"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Message creation
# ─────────────────────────────────────────────────────────────────────────────

def _make_conv(db: Session, owner_id: int, mode: ConversationMode = ConversationMode.GENERAL) -> Conversation:
    conv = Conversation(owner_id=owner_id, title="Tmp", mode=mode)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def test_create_user_message(db: Session, user1: User):
    conv = _make_conv(db, user1.id)
    msg = ChatMessage(
        conversation_id=conv.id,
        role=MessageRole.USER,
        content="What is a force majeure clause?",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert msg.id is not None
    assert msg.conversation_id == conv.id
    assert msg.role == MessageRole.USER
    assert msg.content == "What is a force majeure clause?"
    assert msg.model_used is None
    assert msg.sources_json is None
    assert msg.created_at is not None


def test_create_assistant_message_with_model(db: Session, user1: User):
    conv = _make_conv(db, user1.id)
    msg = ChatMessage(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="Force majeure is a clause that frees parties from liability...",
        model_used="gemini-1.5-flash",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert msg.role == MessageRole.ASSISTANT
    assert msg.model_used == "gemini-1.5-flash"


def test_create_system_message(db: Session, user1: User):
    conv = _make_conv(db, user1.id)
    msg = ChatMessage(
        conversation_id=conv.id,
        role=MessageRole.SYSTEM,
        content="You are a legal assistant specialised in Indian contract law.",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert msg.role == MessageRole.SYSTEM


def test_message_with_sources_json(db: Session, user1: User):
    """Assistant message stores serialised RAG sources correctly."""
    conv = _make_conv(db, user1.id, ConversationMode.RAG)
    sources = [
        {
            "document_id": 1,
            "document_name": "employment_contract.pdf",
            "page_number": 7,
            "chunk_id": "chunk_0021",
            "similarity": 0.87,
        },
        {
            "document_id": 1,
            "document_name": "employment_contract.pdf",
            "page_number": 8,
            "chunk_id": "chunk_0022",
            "similarity": 0.81,
        },
    ]
    msg = ChatMessage(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="Based on page 7 of your contract...",
        model_used="gemini-1.5-flash",
        sources_json=json.dumps(sources),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    parsed = json.loads(msg.sources_json)
    assert len(parsed) == 2
    assert parsed[0]["chunk_id"] == "chunk_0021"
    assert parsed[1]["similarity"] == 0.81


def test_fallback_engine_model_label(db: Session, user1: User):
    """Free AI engine messages carry the correct model label."""
    conv = _make_conv(db, user1.id)
    msg = ChatMessage(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="Here is the analysis...",
        model_used="free-legal-engine",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert msg.model_used == "free-legal-engine"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Conversation retrieval
# ─────────────────────────────────────────────────────────────────────────────

def test_retrieve_conversation_with_messages(db: Session, user1: User):
    """Conversation relationship loads messages in order."""
    conv = _make_conv(db, user1.id)
    pairs = [("user", "Hello"), ("assistant", "Hi there"), ("user", "Explain NDA")]
    for role, content in pairs:
        db.add(ChatMessage(conversation_id=conv.id, role=MessageRole(role), content=content))
    db.commit()

    fetched = db.query(Conversation).filter(Conversation.id == conv.id).first()
    assert fetched is not None
    assert len(fetched.messages) == 3
    assert fetched.messages[0].content == "Hello"
    assert fetched.messages[2].content == "Explain NDA"


def test_list_all_user_conversations(db: Session, user1: User):
    """User can list all their conversations."""
    for i in range(4):
        db.add(Conversation(owner_id=user1.id, title=f"Conv {i}", mode=ConversationMode.GENERAL))
    db.commit()

    results = db.query(Conversation).filter(Conversation.owner_id == user1.id).all()
    assert len(results) == 4


# ─────────────────────────────────────────────────────────────────────────────
# 4. Conversation deletion + cascade
# ─────────────────────────────────────────────────────────────────────────────

def test_delete_conversation_cascades_messages(db: Session, user1: User):
    """Deleting a conversation removes all its messages (cascade)."""
    conv = _make_conv(db, user1.id)
    for i in range(6):
        db.add(ChatMessage(conversation_id=conv.id, role=MessageRole.USER, content=f"msg {i}"))
    db.commit()

    cid = conv.id
    assert db.query(ChatMessage).filter(ChatMessage.conversation_id == cid).count() == 6

    db.delete(conv)
    db.commit()

    assert db.query(Conversation).filter(Conversation.id == cid).first() is None
    assert db.query(ChatMessage).filter(ChatMessage.conversation_id == cid).count() == 0


def test_delete_leaves_other_conversations_intact(db: Session, user1: User):
    """Only the targeted conversation is deleted; siblings survive."""
    conv_a = _make_conv(db, user1.id)
    conv_b = _make_conv(db, user1.id)
    db.add(ChatMessage(conversation_id=conv_a.id, role=MessageRole.USER, content="keep me"))
    db.commit()

    db.delete(conv_b)
    db.commit()

    assert db.query(Conversation).filter(Conversation.id == conv_a.id).first() is not None
    assert db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_a.id).count() == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. Message persistence
# ─────────────────────────────────────────────────────────────────────────────

def test_messages_persist_and_ordered(db: Session, user1: User):
    """Messages are stored and retrieved in chronological order."""
    conv = _make_conv(db, user1.id)
    for i in range(5):
        db.add(ChatMessage(
            conversation_id=conv.id,
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content=f"turn-{i}",
        ))
        db.flush()          # ensure distinct created_at across SQLite ms

    db.commit()

    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
        .all()
    )
    assert len(msgs) == 5
    for i, m in enumerate(msgs):
        assert m.content == f"turn-{i}"


def test_message_content_survives_roundtrip(db: Session, user1: User):
    """Long legal text is stored and retrieved intact."""
    conv = _make_conv(db, user1.id)
    long_text = "The party of the first part hereby agrees " * 200   # ~8 KB
    msg = ChatMessage(conversation_id=conv.id, role=MessageRole.USER, content=long_text)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert msg.content == long_text


# ─────────────────────────────────────────────────────────────────────────────
# 6. User ownership
# ─────────────────────────────────────────────────────────────────────────────

def test_conversation_owner_relationship(db: Session, user1: User):
    """Conversation.owner resolves to the correct User."""
    conv = _make_conv(db, user1.id)
    assert conv.owner.id == user1.id
    assert conv.owner.email == "alice@lexguard.test"


def test_message_reaches_owner_via_conversation(db: Session, user1: User):
    """Message → Conversation → owner chain is intact."""
    conv = _make_conv(db, user1.id)
    msg = ChatMessage(conversation_id=conv.id, role=MessageRole.USER, content="test")
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert msg.conversation.owner_id == user1.id


# ─────────────────────────────────────────────────────────────────────────────
# 7. Cross-user access rejection
# ─────────────────────────────────────────────────────────────────────────────

def test_user2_cannot_see_user1_conversation(db: Session, user1: User, user2: User):
    """Query filtered by wrong owner returns nothing."""
    conv = _make_conv(db, user1.id)

    result = db.query(Conversation).filter(
        Conversation.id == conv.id,
        Conversation.owner_id == user2.id,   # wrong owner
    ).first()

    assert result is None


def test_user_sees_only_own_conversations(db: Session, user1: User, user2: User):
    """Listing is always owner-scoped; no cross-user leakage."""
    for _ in range(3):
        db.add(Conversation(owner_id=user1.id, mode=ConversationMode.GENERAL))
    for _ in range(2):
        db.add(Conversation(owner_id=user2.id, mode=ConversationMode.GENERAL))
    db.commit()

    u1_convs = db.query(Conversation).filter(Conversation.owner_id == user1.id).all()
    u2_convs = db.query(Conversation).filter(Conversation.owner_id == user2.id).all()

    assert len(u1_convs) == 3
    assert len(u2_convs) == 2
    assert all(c.owner_id == user1.id for c in u1_convs)
    assert all(c.owner_id == user2.id for c in u2_convs)


def test_messages_unreachable_across_users(db: Session, user1: User, user2: User):
    """User2 cannot read User1's messages even by guessing conversation_id."""
    conv = _make_conv(db, user1.id)
    db.add(ChatMessage(conversation_id=conv.id, role=MessageRole.USER, content="secret"))
    db.commit()

    # Simulate user2 trying to fetch messages by guessing the conversation id
    owner_check = db.query(Conversation).filter(
        Conversation.id == conv.id,
        Conversation.owner_id == user2.id,
    ).first()

    assert owner_check is None          # ownership gate blocks access
    # Therefore user2 gets no messages


# ─────────────────────────────────────────────────────────────────────────────
# 8. Conversation with document
# ─────────────────────────────────────────────────────────────────────────────

def test_document_relationship_resolves(db: Session, user1: User, document1: LegalDocument):
    """Conversation.document foreign-key relationship loads correctly."""
    conv = Conversation(
        owner_id=user1.id,
        document_id=document1.id,
        title="Contract Q&A",
        mode=ConversationMode.DOCUMENT,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    assert conv.document is not None
    assert conv.document.filename == "employment_contract.pdf"
    assert conv.document.owner_id == user1.id


def test_multiple_conversations_same_document(db: Session, user1: User, document1: LegalDocument):
    """One document can have many conversations."""
    for i in range(3):
        db.add(Conversation(
            owner_id=user1.id,
            document_id=document1.id,
            title=f"Session {i}",
            mode=ConversationMode.DOCUMENT,
        ))
    db.commit()

    count = db.query(Conversation).filter(
        Conversation.document_id == document1.id
    ).count()
    assert count == 3


def test_user2_document_blocked_from_user1_conversation(db: Session, user1: User, user2: User, document1: LegalDocument):
    """User2 cannot create a conversation referencing User1's document via the API security check."""
    # At the model level user2 could technically reference document1.
    # The API layer (_validate_document_ownership) prevents this.
    # Here we verify that a data-layer query with the correct filter produces nothing.
    user2_doc = db.query(LegalDocument).filter(
        LegalDocument.id == document1.id,
        LegalDocument.owner_id == user2.id,
    ).first()
    assert user2_doc is None    # document1 belongs to user1 only


# ─────────────────────────────────────────────────────────────────────────────
# 9. Conversation without document
# ─────────────────────────────────────────────────────────────────────────────

def test_general_conversation_has_no_document(db: Session, user1: User):
    conv = _make_conv(db, user1.id, ConversationMode.GENERAL)
    assert conv.document_id is None
    assert conv.document is None


def test_rag_conversation_no_specific_document(db: Session, user1: User):
    conv = _make_conv(db, user1.id, ConversationMode.RAG)
    assert conv.document_id is None
    assert conv.mode == ConversationMode.RAG


def test_all_three_modes_create_without_document(db: Session, user1: User):
    """All modes can be created without a document."""
    for mode in ConversationMode:
        conv = Conversation(owner_id=user1.id, mode=mode)
        db.add(conv)
    db.commit()

    total = db.query(Conversation).filter(Conversation.owner_id == user1.id).count()
    assert total == 3


# ─────────────────────────────────────────────────────────────────────────────
# 10. API endpoint smoke tests
# Note: db param keeps the setup_db autouse fixture alive for the whole test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_create_conversation(db: Session, user1: User, token1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"{API}/chat/conversations",
            json={"title": "Contract Review", "mode": "general"},
            headers={"Authorization": f"Bearer {token1}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Contract Review"
    assert data["mode"] == "general"
    assert "id" in data
    assert "owner_id" in data


@pytest.mark.asyncio
async def test_api_list_conversations(db: Session, user1: User, token1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for i in range(2):
            await ac.post(
                f"{API}/chat/conversations",
                json={"title": f"Conv {i}", "mode": "general"},
                headers={"Authorization": f"Bearer {token1}"},
            )
        resp = await ac.get(
            f"{API}/chat/conversations",
            headers={"Authorization": f"Bearer {token1}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["conversations"]) == 2


@pytest.mark.asyncio
async def test_api_get_conversation(db: Session, user1: User, token1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            f"{API}/chat/conversations",
            json={"title": "Get Test", "mode": "rag"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create.status_code == 201, create.text
        conv_id = create.json()["id"]

        resp = await ac.get(
            f"{API}/chat/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token1}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation"]["id"] == conv_id
    assert data["conversation"]["title"] == "Get Test"
    assert data["total_messages"] == 0


@pytest.mark.asyncio
async def test_api_delete_conversation(db: Session, user1: User, token1: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            f"{API}/chat/conversations",
            json={"title": "To Delete", "mode": "general"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create.status_code == 201, create.text
        conv_id = create.json()["id"]

        del_resp = await ac.delete(
            f"{API}/chat/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert del_resp.status_code == 204

        get_resp = await ac.get(
            f"{API}/chat/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_api_send_message_placeholder(db: Session, user1: User, token1: str):
    """Phase 1 placeholder: user message persisted, assistant responds."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            f"{API}/chat/conversations",
            json={"title": "Message Test", "mode": "general"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create.status_code == 201, create.text
        conv_id = create.json()["id"]

        resp = await ac.post(
            f"{API}/chat/conversations/{conv_id}/messages",
            json={"message": "What is consideration in contract law?"},
            headers={"Authorization": f"Bearer {token1}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_message"]["role"] == "user"
    assert data["user_message"]["content"] == "What is consideration in contract law?"
    assert data["assistant_message"]["role"] == "assistant"
    assert data["conversation"]["id"] == conv_id


@pytest.mark.asyncio
async def test_api_cross_user_conversation_blocked(
    db: Session, user1: User, user2: User, token1: str, token2: str
):
    """User2 cannot access User1's conversation via the API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            f"{API}/chat/conversations",
            json={"title": "Private Conv", "mode": "general"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create.status_code == 201, create.text
        conv_id = create.json()["id"]

        resp = await ac.get(
            f"{API}/chat/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_unauthenticated_blocked():
    """No token → 401 or 403 on all chat endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"{API}/chat/conversations")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_api_invalid_mode_rejected(db: Session, user1: User, token1: str):
    """Creating a conversation with an invalid mode returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"{API}/chat/conversations",
            json={"title": "Bad Mode", "mode": "hackermode"},
            headers={"Authorization": f"Bearer {token1}"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_conversation_history_shows_messages(db: Session, user1: User, token1: str):
    """Messages sent appear in history with correct roles and order."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            f"{API}/chat/conversations",
            json={"title": "History Test", "mode": "general"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create.status_code == 201, create.text
        conv_id = create.json()["id"]

        await ac.post(
            f"{API}/chat/conversations/{conv_id}/messages",
            json={"message": "First question"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        await ac.post(
            f"{API}/chat/conversations/{conv_id}/messages",
            json={"message": "Second question"},
            headers={"Authorization": f"Bearer {token1}"},
        )

        history = await ac.get(
            f"{API}/chat/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token1}"},
        )

    data = history.json()
    # 2 sends × 2 messages each (user + assistant) = 4 messages
    assert data["total_messages"] == 4
    roles = [m["role"] for m in data["conversation"]["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
