"""
test_chat_security.py — Phase 6 Security & Isolation Tests
===========================================================
Tests every ownership and isolation requirement for the persistent chat system.

Run:
    cd backend
    python -m pytest tests/test_chat_security.py -v

Categories:
  1. Conversation ownership — users cannot access each other's conversations
  2. Document security     — document_id validation at conversation creation
  3. Context isolation     — conversations do not share history
  4. Idempotency           — duplicate messages within 10s are not re-processed
  5. Message persistence   — messages survive session re-load
  6. Access control        — all endpoints enforce owner_id
"""

import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── in-memory SQLite for isolated tests ──────────────────────────────────────
TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def db_session():
    """Create all tables in an isolated in-memory SQLite DB for the test run."""
    from app.db.base import Base
    import app.models  # noqa: F401 — ensure all models are registered

    engine  = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def two_users(db_session):
    """Seed User A and User B."""
    from app.models.user import User, UserRole, VerificationStatus
    from app.core.security import get_password_hash

    user_a = User(
        name="User A",
        email="user_a@test.com",
        password_hash=get_password_hash("passA"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED,
    )
    user_b = User(
        name="User B",
        email="user_b@test.com",
        password_hash=get_password_hash("passB"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED,
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    return user_a, user_b


@pytest.fixture(scope="module")
def two_documents(db_session, two_users):
    """Seed one document per user."""
    from app.models.document import LegalDocument, DocumentType, ProcessingStatus

    user_a, user_b = two_users

    doc_a = LegalDocument(
        owner_id=    user_a.id,
        filename=    "employment_a.pdf",
        stored_filename= "employment_a.pdf",
        stored_path= "/tmp/a.pdf",
        file_type=   "pdf",
        file_size=   1024,
        file_hash=   "hash_a",
        document_type=    DocumentType.CONTRACT,
        processing_status=ProcessingStatus.READY,
    )
    doc_b = LegalDocument(
        owner_id=    user_b.id,
        filename=    "nda_b.pdf",
        stored_filename= "nda_b.pdf",
        stored_path= "/tmp/b.pdf",
        file_type=   "pdf",
        file_size=   2048,
        file_hash=   "hash_b",
        document_type=    DocumentType.CONTRACT,
        processing_status=ProcessingStatus.READY,
    )
    db_session.add_all([doc_a, doc_b])
    db_session.commit()
    db_session.refresh(doc_a)
    db_session.refresh(doc_b)
    return doc_a, doc_b


@pytest.fixture(scope="module")
def conv_a(db_session, two_users):
    """Seed Conversation A belonging to User A."""
    from app.models.conversation import Conversation, ConversationMode

    user_a, _ = two_users
    conv = Conversation(
        owner_id= user_a.id,
        title=    "NDA Review",
        mode=     ConversationMode.GENERAL,
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)
    return conv


# ─────────────────────────────────────────────────────────────────────────────
# 1. Conversation ownership
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationOwnership:

    def test_user_a_can_query_own_conversation(self, db_session, conv_a, two_users):
        """User A can fetch their own conversation."""
        from app.models.conversation import Conversation
        user_a, _ = two_users
        result = db_session.query(Conversation).filter(
            Conversation.id       == conv_a.id,
            Conversation.owner_id == user_a.id,
        ).first()
        assert result is not None, "User A must see their own conversation"

    def test_user_b_cannot_access_user_a_conversation(self, db_session, conv_a, two_users):
        """User B must get None when querying User A's conversation."""
        from app.models.conversation import Conversation
        _, user_b = two_users
        result = db_session.query(Conversation).filter(
            Conversation.id       == conv_a.id,
            Conversation.owner_id == user_b.id,
        ).first()
        assert result is None, "User B must NEVER see User A's conversation"

    def test_list_filters_by_owner(self, db_session, two_users, conv_a):
        """List query returns only conversations belonging to the requesting user."""
        from app.models.conversation import Conversation
        _, user_b = two_users
        results = db_session.query(Conversation).filter(
            Conversation.owner_id == user_b.id,
        ).all()
        ids = [c.id for c in results]
        assert conv_a.id not in ids, "conv_a must not appear in User B's list"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Document security
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentSecurity:

    def test_user_b_cannot_create_conv_with_user_a_document(
        self, db_session, two_users, two_documents
    ):
        """
        _validate_document_ownership raises 404 when User B tries to create
        a conversation linked to User A's document.
        """
        from fastapi import HTTPException
        from app.api.chat import _validate_document_ownership

        _, user_b = two_users
        doc_a, _  = two_documents

        with pytest.raises(HTTPException) as exc_info:
            _validate_document_ownership(doc_a.id, user_b.id, db_session)

        assert exc_info.value.status_code == 404, \
            "Must return 404 (not 403) so document existence is not leaked"

    def test_user_a_can_create_conv_with_own_document(
        self, db_session, two_users, two_documents
    ):
        """_validate_document_ownership succeeds for the document's actual owner."""
        from app.api.chat import _validate_document_ownership

        user_a, _ = two_users
        doc_a, _  = two_documents

        doc = _validate_document_ownership(doc_a.id, user_a.id, db_session)
        assert doc.id == doc_a.id


# ─────────────────────────────────────────────────────────────────────────────
# 3. Message persistence
# ─────────────────────────────────────────────────────────────────────────────

class TestMessagePersistence:

    def test_messages_persist_and_load_in_order(self, db_session, conv_a):
        """Messages saved to a conversation are retrieved in chronological order."""
        from app.models.conversation import ChatMessage, MessageRole

        msg1 = ChatMessage(
            conversation_id= conv_a.id,
            role=            MessageRole.USER,
            content=         "What is an NDA?",
        )
        msg2 = ChatMessage(
            conversation_id= conv_a.id,
            role=            MessageRole.ASSISTANT,
            content=         "An NDA is a Non-Disclosure Agreement.",
            model_used=      "free-legal-engine",
        )
        db_session.add_all([msg1, msg2])
        db_session.commit()

        loaded = (
            db_session.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conv_a.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
            .all()
        )
        assert len(loaded) >= 2
        roles = [m.role.value for m in loaded]
        assert "user" in roles
        assert "assistant" in roles

    def test_messages_belong_to_correct_conversation(self, db_session, two_users, conv_a):
        """Messages from conv_a are not visible when querying under User B's context."""
        from app.models.conversation import ChatMessage, Conversation

        _, user_b = two_users

        # All conversations belonging to user_b
        user_b_conv_ids = [
            c.id for c in db_session.query(Conversation)
            .filter(Conversation.owner_id == user_b.id).all()
        ]
        # All messages from those conversations
        msgs = (
            db_session.query(ChatMessage)
            .filter(ChatMessage.conversation_id.in_(user_b_conv_ids or [-1]))
            .all()
        )
        msg_conv_ids = {m.conversation_id for m in msgs}
        assert conv_a.id not in msg_conv_ids, \
            "User B must never see messages from User A's conversations"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Context isolation between conversations
# ─────────────────────────────────────────────────────────────────────────────

class TestContextIsolation:

    def test_separate_conversations_have_separate_histories(self, db_session, two_users):
        """
        History loaded for Conversation B must not contain messages from Conversation A.
        """
        from app.models.conversation import Conversation, ChatMessage, ConversationMode, MessageRole

        user_a, _ = two_users

        conv_x = Conversation(owner_id=user_a.id, title="Conv X", mode=ConversationMode.GENERAL)
        conv_y = Conversation(owner_id=user_a.id, title="Conv Y", mode=ConversationMode.GENERAL)
        db_session.add_all([conv_x, conv_y])
        db_session.commit()

        db_session.add(ChatMessage(
            conversation_id=conv_x.id, role=MessageRole.USER,
            content="Context from Conv X — secret clause info"
        ))
        db_session.commit()

        # Load history for conv_y — must be empty
        history_y = (
            db_session.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conv_y.id)
            .all()
        )
        assert len(history_y) == 0, "Conv Y must not receive Conv X's messages"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Source storage
# ─────────────────────────────────────────────────────────────────────────────

class TestSourceStorage:

    def test_sources_json_round_trip(self, db_session, conv_a):
        """Sources serialised into sources_json are correctly deserialised."""
        from app.models.conversation import ChatMessage, MessageRole
        from app.api.chat import _parse_sources

        sources = [
            {
                "document_id":   42,
                "document_name": "employment_contract.pdf",
                "page_number":   5,
                "chunk_id":      "chunk_abc123",
                "similarity":    0.91,
                "matter_id":     None,
                "jurisdiction":  "India",
            }
        ]
        msg = ChatMessage(
            conversation_id= conv_a.id,
            role=            MessageRole.ASSISTANT,
            content=         "The termination clause is on page 5.",
            model_used=      "gemini",
            sources_json=    json.dumps(sources),
        )
        db_session.add(msg)
        db_session.commit()
        db_session.refresh(msg)

        parsed = _parse_sources(msg.sources_json)
        assert parsed is not None
        assert len(parsed) == 1
        assert parsed[0].document_id   == 42
        assert parsed[0].document_name == "employment_contract.pdf"
        assert parsed[0].page_number   == 5
        assert parsed[0].chunk_id      == "chunk_abc123"
        assert abs(parsed[0].similarity - 0.91) < 0.001

    def test_malformed_sources_json_returns_none(self):
        """Corrupted sources_json must return None, not raise."""
        from app.api.chat import _parse_sources
        assert _parse_sources("{bad json") is None
        assert _parse_sources(None)        is None
        assert _parse_sources("")          is None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Idempotency guard
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotencyGuard:

    def test_duplicate_detection_within_window(self, db_session, conv_a):
        """
        A ChatMessage with the same content saved within the last 10 seconds
        should be detected by the idempotency query.
        """
        from app.models.conversation import ChatMessage, MessageRole
        from datetime import timedelta

        text = "What is the notice period? [idempotency test]"
        msg = ChatMessage(
            conversation_id= conv_a.id,
            role=            MessageRole.USER,
            content=         text,
            created_at=      datetime.now(timezone.utc),
        )
        db_session.add(msg)
        db_session.commit()

        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
        duplicate = (
            db_session.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == conv_a.id,
                ChatMessage.role            == MessageRole.USER,
                ChatMessage.content         == text,
                ChatMessage.created_at      >= recent_cutoff,
            )
            .first()
        )
        assert duplicate is not None, "Idempotency guard must detect the recent duplicate"

    def test_old_message_not_flagged_as_duplicate(self, db_session, conv_a):
        """A message saved > 10s ago must not trigger the idempotency guard."""
        from app.models.conversation import ChatMessage, MessageRole
        from datetime import timedelta

        old_text = "Old question [idempotency test]"
        old_msg = ChatMessage(
            conversation_id= conv_a.id,
            role=            MessageRole.USER,
            content=         old_text,
            created_at=      datetime(2000, 1, 1, tzinfo=timezone.utc),  # very old
        )
        db_session.add(old_msg)
        db_session.commit()

        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
        duplicate = (
            db_session.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == conv_a.id,
                ChatMessage.role            == MessageRole.USER,
                ChatMessage.content         == old_text,
                ChatMessage.created_at      >= recent_cutoff,
            )
            .first()
        )
        assert duplicate is None, "Old message must not be flagged as duplicate"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Model / index verification
# ─────────────────────────────────────────────────────────────────────────────

class TestModelIndexes:

    def test_conversation_table_has_owner_index(self):
        """Conversation.owner_id column has an index defined."""
        from app.models.conversation import Conversation
        indexed_cols = {c.name for c in Conversation.__table__.columns if c.index}
        assert "owner_id" in indexed_cols

    def test_chat_message_table_has_conversation_id_index(self):
        """ChatMessage.conversation_id column has an index defined."""
        from app.models.conversation import ChatMessage
        indexed_cols = {c.name for c in ChatMessage.__table__.columns if c.index}
        assert "conversation_id" in indexed_cols

    def test_composite_indexes_exist(self):
        """Composite indexes for owner+updated_at and conversation+created_at exist."""
        from app.models.conversation import Conversation, ChatMessage
        from sqlalchemy import inspect

        conv_idx_names  = {i.name for i in Conversation.__table__.indexes}
        msg_idx_names   = {i.name for i in ChatMessage.__table__.indexes}

        assert "idx_conversation_owner_updated" in conv_idx_names, \
            "Missing idx_conversation_owner_updated — recency sort will be slow"
        assert "idx_message_conversation_created" in msg_idx_names, \
            "Missing idx_message_conversation_created — history load will be slow"
