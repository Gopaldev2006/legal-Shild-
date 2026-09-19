"""
Chat API — Phase 2: Persistent Conversations with Real AI

Endpoints:
  POST   /api/v1/chat/conversations                    Create new conversation
  GET    /api/v1/chat/conversations                    List user's conversations (sorted by recent activity)
  GET    /api/v1/chat/conversations/{id}               Full conversation + messages
  PATCH  /api/v1/chat/conversations/{id}               Rename title
  DELETE /api/v1/chat/conversations/{id}               Delete conversation + cascade messages
  POST   /api/v1/chat/conversations/{id}/messages      Send message → AI responds → both persisted

AI Routing (based on conversation.mode):
  general  → rag_service.process_public_query()   (Gemini or Free AI Legal Engine)
  document → rag_answer()                          (RAG scoped to one document)
  rag      → rag_answer()                          (RAG across all user's documents)

Security:
  All endpoints require JWT authentication.
  Every query filters by Conversation.owner_id == current_user.id.
  Document ownership validated before conversation creation.
  404 returned for wrong-owner access (never leaks existence).
"""

import json
import logging
import re
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.user import User
from app.models.conversation import Conversation, ChatMessage, ConversationMode, MessageRole
from app.models.document import LegalDocument
from app.api.deps import get_db, get_current_user
from app.core.permissions import require_professional
from app.core.security import decrypt_api_key
from app.core.limiter import limiter
from app.core.config import settings as app_settings
from app.services.audit.audit_service import write_audit_event
from app.models.audit_log import AuditEventType
from app.services.rag.rag_service import rag_service
from app.services.rag.rag_answer_service import rag_answer
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListItem,
    ConversationListResponse,
    ConversationDetail,
    ConversationHistoryResponse,
    ChatMessageResponse,
    MessageSourceSchema,
    SendMessageRequest,
    SendMessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Persistent Chat"])


# ============================================================================
# Auto-Title Generation (deterministic, no AI call)
# ============================================================================

# Common legal stop-words to strip before picking title words
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "on",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "from",
    "up", "down", "out", "off", "over", "under", "again", "and", "but",
    "or", "nor", "so", "yet", "both", "either", "neither", "not", "no",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
    "his", "her", "its", "they", "their", "them", "how", "when", "where",
    "why", "there", "here", "just", "any", "all", "more", "also", "please",
    "tell", "explain", "describe", "give", "me", "us", "can", "provide",
    "list", "show", "find", "get", "make", "help",
})

# High-signal legal keywords that make strong titles
_LEGAL_KEYWORDS = {
    "termination", "contract", "clause", "section", "article", "agreement",
    "employment", "lease", "liability", "indemnity", "breach", "penalty",
    "payment", "renewal", "notice", "jurisdiction", "force", "majeure",
    "confidentiality", "nda", "intellectual", "property", "copyright",
    "trademark", "patent", "dispute", "arbitration", "mediation", "court",
    "remedy", "damages", "obligation", "rights", "duties", "party", "parties",
    "landlord", "tenant", "employer", "employee", "vendor", "client",
    "warranty", "guarantee", "default", "consideration", "offer", "acceptance",
    "amendment", "assignment", "subcontract", "compliance", "regulation",
    "statute", "act", "law", "legal", "bail", "evidence", "witness",
    "criminal", "civil", "appeal", "judgment", "verdict", "compensation",
}


def generate_title(message: str, max_words: int = 4) -> str:
    """
    Generate a short, readable conversation title from the first user message.

    Strategy (deterministic, zero AI calls):
    1. Strip punctuation, lowercase, split into words.
    2. Prefer high-signal legal keywords found in the message (up to max_words).
    3. Fall back to the first non-stop-word tokens (up to max_words).
    4. Title-case the result.
    5. Hard-cap at 60 characters.

    Examples:
      "What are the termination conditions?"       → "Termination Conditions"
      "Explain Section 420 IPC"                    → "Section 420 IPC"
      "Is force majeure applicable here?"          → "Force Majeure"
      "Hello"                                      → "New Conversation"
    """
    if not message or not message.strip():
        return "New Conversation"

    # Normalise: lowercase, strip non-alphanumeric except spaces
    cleaned = re.sub(r"[^a-z0-9\s]", " ", message.lower())
    words = cleaned.split()

    if not words:
        return "New Conversation"

    # Priority 1: legal keywords found in the message (preserve original casing later)
    legal_hits = [w for w in words if w in _LEGAL_KEYWORDS]

    # Priority 2: non-stop-word content words
    content_words = [w for w in words if w not in _STOP_WORDS and len(w) > 2]

    chosen = legal_hits[:max_words] if legal_hits else content_words[:max_words]

    if not chosen:
        # Last resort: just first two words from original
        chosen = words[:2]

    title = " ".join(chosen).title()
    return title[:60] if title else "New Conversation"


# ============================================================================
# AI Dispatch Layer
# ============================================================================

def _get_user_gemini_key(user: User) -> Optional[str]:
    """Return decrypted personal Gemini key for the user, or None."""
    if not user.encrypted_gemini_api_key:
        return None
    return decrypt_api_key(user.encrypted_gemini_api_key)


def _call_general_ai(query: str, user: User) -> tuple[str, str]:
    """
    Route general-mode query through process_public_query.
    Returns (answer_text, provider_used).
    Uses user's personal Gemini key if available, otherwise system key or free engine.
    """
    user_api_key = _get_user_gemini_key(user)
    result = rag_service.process_public_query(query=query, user_api_key=user_api_key)

    answer = result.get("answer", "")
    topic  = result.get("topic", "AI Legal Educational Assistant")

    # Map topic to a concise provider label
    if "Gemini" in topic:
        provider = "gemini"
    else:
        provider = "free-legal-engine"

    return answer, provider


def _call_rag_ai(
    query:       str,
    user:        User,
    db:          Session,
    document_id: Optional[int] = None,
    history:     Optional[list] = None,
) -> tuple[str, str, list]:
    """
    Route document/rag-mode query through rag_answer.
    Returns (answer_text, provider_used, sources_list).
    sources_list items match MessageSourceSchema field names.
    history: list of {"role": str, "content": str} dicts for multi-turn context.
    """
    result = rag_answer(
        query=                query,
        user_id=              user.id,
        db=                   db,
        document_id=          document_id,
        conversation_history= history,
    )

    # Convert SourceItem dataclasses → plain dicts for JSON storage
    sources = [
        {
            "document_id":   s.document_id,
            "document_name": s.filename,
            "page_number":   s.page_number,
            "chunk_id":      s.chunk_id,
            "similarity":    round(s.similarity, 4),
            "matter_id":     s.matter_id,
            "jurisdiction":  s.jurisdiction,
        }
        for s in result.sources
    ]

    # Normalise provider label
    provider = result.provider_used
    if "Gemini" in provider:
        provider = "gemini"
    elif "Free" in provider or "Grounded" in provider:
        provider = "free-legal-engine"

    return result.answer, provider, sources


def _dispatch_ai(
    conversation: Conversation,
    message:      str,
    user:         User,
    db:           Session,
) -> tuple[str, str, Optional[list]]:
    """
    Route message to correct AI engine based on conversation mode.
    Loads recent conversation history for RAG/document modes to enable
    multi-turn context-aware answers.

    Returns:
        (answer_text, provider_used, sources_or_None)
    """
    mode = conversation.mode

    if mode == ConversationMode.GENERAL:
        answer, provider = _call_general_ai(message, user)
        return answer, provider, None

    # ── Build recent history for RAG/document modes ───────────────────────────
    max_history = getattr(settings, "CHAT_MAX_HISTORY_MESSAGES", 20)
    recent_msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(desc(ChatMessage.created_at))
        .limit(max_history)
        .all()
    )
    # Reverse so chronological order, exclude the message we just flushed (USER role)
    history = [
        {"role": m.role.value, "content": m.content}
        for m in reversed(recent_msgs)
        if m.role.value in ("user", "assistant")
    ]

    if mode == ConversationMode.DOCUMENT:
        answer, provider, sources = _call_rag_ai(
            query=       message,
            user=        user,
            db=          db,
            document_id= conversation.document_id,
            history=     history,
        )
        return answer, provider, sources

    elif mode == ConversationMode.RAG:
        answer, provider, sources = _call_rag_ai(
            query=   message,
            user=    user,
            db=      db,
            history= history,
        )
        return answer, provider, sources

    else:
        answer, provider = _call_general_ai(message, user)
        return answer, provider, None


# ============================================================================
# Internal Helpers
# ============================================================================

def _get_conversation_or_404(conversation_id: int, user_id: int, db: Session) -> Conversation:
    """
    Fetch conversation by ID with owner check.
    Returns 404 for both missing AND wrong-owner (never leaks existence).
    """
    conv = db.query(Conversation).filter(
        Conversation.id       == conversation_id,
        Conversation.owner_id == user_id,
    ).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conv


def _validate_document_ownership(document_id: int, user_id: int, db: Session) -> LegalDocument:
    """
    Verify document exists and belongs to user.
    Returns 404 for both missing AND wrong-owner.
    """
    doc = db.query(LegalDocument).filter(
        LegalDocument.id       == document_id,
        LegalDocument.owner_id == user_id,
    ).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return doc


def _parse_sources(sources_json: Optional[str]) -> Optional[List[MessageSourceSchema]]:
    """Deserialise sources_json column → list of MessageSourceSchema."""
    if not sources_json:
        return None
    try:
        data = json.loads(sources_json)
        return [MessageSourceSchema(**s) for s in data]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _message_to_schema(msg: ChatMessage) -> ChatMessageResponse:
    """Convert ORM ChatMessage → ChatMessageResponse (with parsed sources)."""
    return ChatMessageResponse(
        id=              msg.id,
        conversation_id= msg.conversation_id,
        role=            msg.role.value,
        content=         msg.content,
        model_used=      msg.model_used,
        sources=         _parse_sources(msg.sources_json),
        created_at=      msg.created_at,
    )


def _conversation_list_item(conv: Conversation, db: Session) -> ConversationListItem:
    """Build a ConversationListItem with message count + last-message timestamp."""
    count = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.conversation_id == conv.id
    ).scalar() or 0

    last = (
        db.query(ChatMessage.created_at)
        .filter(ChatMessage.conversation_id == conv.id)
        .order_by(desc(ChatMessage.created_at))
        .limit(1)
        .scalar()
    )

    return ConversationListItem(
        id=              conv.id,
        owner_id=        conv.owner_id,
        document_id=     conv.document_id,
        title=           conv.title,
        mode=            conv.mode.value,
        message_count=   count,
        last_message_at= last,
        created_at=      conv.created_at,
        updated_at=      conv.updated_at,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
@limiter.limit(lambda: app_settings.RATE_LIMIT_CHAT_CREATE)
def create_conversation(
    request:      Request,
    payload:      ConversationCreate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Create a persistent conversation thread.

    - **general** mode  — available to any authenticated user
    - **document** mode — requires Verified Legal Professional or Admin
    - **rag** mode      — requires Verified Legal Professional or Admin

    Title is optional. Auto-updated on the first message.
    """
    # document and rag modes require professional access
    if payload.mode in ("document", "rag"):
        require_professional(current_user)

    # Validate document ownership when document_id provided
    if payload.document_id is not None:
        if payload.mode not in ("document", "rag"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="document_id can only be set for 'document' or 'rag' mode conversations",
            )
        _validate_document_ownership(payload.document_id, current_user.id, db)

    conv = Conversation(
        owner_id=    current_user.id,
        document_id= payload.document_id,
        title=       payload.title,
        mode=        ConversationMode(payload.mode),
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    # Audit: CHAT_CREATED
    write_audit_event(
        db=db, event_type=AuditEventType.CHAT_CREATED,
        user_id=current_user.id, resource_type="chat", resource_id=conv.id,
        success=True, ip_address=request.client.host if request.client else None,
        metadata={"mode": payload.mode, "document_id": payload.document_id},
    )
    return ConversationResponse.model_validate(conv)


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List user's conversations",
)
def list_conversations(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
    page:      int           = Query(1,  ge=1,   description="Page number (1-based)"),
    page_size: int           = Query(20, ge=1, le=100, description="Items per page"),
    mode:      Optional[str] = Query(None, description="Filter by mode: general | document | rag"),
):
    """
    Return the current user's conversations sorted by most-recently-updated first.
    Supports pagination and optional mode filter.
    """
    q = db.query(Conversation).filter(Conversation.owner_id == current_user.id)

    if mode:
        try:
            q = q.filter(Conversation.mode == ConversationMode(mode))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode '{mode}'. Must be: general, document, rag",
            )

    total = q.count()
    convs = q.order_by(desc(Conversation.updated_at)).offset((page - 1) * page_size).limit(page_size).all()

    items = [_conversation_list_item(c, db) for c in convs]

    return ConversationListResponse(
        conversations= items,
        total=         total,
        page=          page,
        page_size=     page_size,
        has_more=      (page * page_size) < total,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationHistoryResponse,
    summary="Get full conversation with all messages",
)
def get_conversation(
    conversation_id: int,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db),
):
    """
    Return conversation metadata and full message history (chronological order).
    Includes document filename when a document is associated.
    """
    conv = _get_conversation_or_404(conversation_id, current_user.id, db)

    doc_filename = None
    if conv.document_id:
        doc = db.query(LegalDocument.filename).filter(LegalDocument.id == conv.document_id).scalar()
        doc_filename = doc

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
        .all()
    )

    msg_schemas = [_message_to_schema(m) for m in messages]

    detail = ConversationDetail(
        id=                conv.id,
        owner_id=          conv.owner_id,
        document_id=       conv.document_id,
        document_filename= doc_filename,
        title=             conv.title,
        mode=              conv.mode.value,
        messages=          msg_schemas,
        created_at=        conv.created_at,
        updated_at=        conv.updated_at,
    )
    return ConversationHistoryResponse(
        conversation=   detail,
        total_messages= len(messages),
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation title",
)
def update_conversation(
    conversation_id: int,
    payload:         ConversationUpdate,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db),
):
    """Rename a conversation. Only the owner may update it."""
    conv = _get_conversation_or_404(conversation_id, current_user.id, db)

    if payload.title is not None:
        conv.title = payload.title.strip() or conv.title

    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation and all its messages",
)
def delete_conversation(
    conversation_id: int,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db),
):
    """
    Permanently delete a conversation and cascade-delete its messages.
    Associated document is NOT deleted — only the chat association.
    """
    conv = _get_conversation_or_404(conversation_id, current_user.id, db)
    db.delete(conv)
    db.commit()
    # Audit: CHAT_DELETED
    write_audit_event(
        db=db, event_type=AuditEventType.CHAT_DELETED,
        user_id=current_user.id, resource_type="chat", resource_id=conversation_id,
        success=True,
    )
    return None


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    summary="Send a message and receive an AI response",
)
@limiter.limit(lambda: app_settings.RATE_LIMIT_CHAT_MESSAGE)
def send_message(
    request:         Request,
    conversation_id: int,
    payload:         SendMessageRequest,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db),
):
    """
    Full persistent message flow:

    1. Authenticate user and verify conversation ownership.
    2. Validate and persist the user message.
    3. Auto-generate conversation title on first message (if still default).
    4. Dispatch to the correct AI engine based on `conversation.mode`.
    5. Persist the AI response with source tracking.
    6. Update `conversation.updated_at` for recency sorting.
    7. Return both messages.

    **AI routing:**
    - `general`  → Public AI assistant (Gemini or Free Legal Engine)
    - `document` → RAG scoped to the conversation's linked document
    - `rag`      → RAG across all user's uploaded documents

    Sources are stored as JSON and returned for document/rag modes.
    """
    conv = _get_conversation_or_404(conversation_id, current_user.id, db)

    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    # ── Idempotency guard: reject if a user message with identical content
    #    was saved in the last 10 seconds (catches double-click / network retry)
    from datetime import timedelta
    recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
    duplicate = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.role            == MessageRole.USER,
            ChatMessage.content         == user_text,
            ChatMessage.created_at      >= recent_cutoff,
        )
        .first()
    )
    if duplicate:
        # Return the already-persisted pair silently instead of re-running AI
        msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(2)
            .all()
        )
        msgs = list(reversed(msgs))
        if len(msgs) == 2:
            return SendMessageResponse(
                user_message=      _message_to_schema(msgs[0]),
                assistant_message= _message_to_schema(msgs[1]),
                conversation=      ConversationResponse.model_validate(conv),
            )

    # ── 1. Save user message ─────────────────────────────────────────────────
    user_msg = ChatMessage(
        conversation_id= conversation_id,
        role=            MessageRole.USER,
        content=         user_text,
    )
    db.add(user_msg)
    db.flush()   # get user_msg.id without full commit

    # ── 2. Auto-title: update if still the default placeholder ───────────────
    if conv.title in ("New Conversation", "", None):
        conv.title = generate_title(user_text)

    # ── 3. Dispatch to AI engine ─────────────────────────────────────────────
    # Log at info level — DO NOT log message content (privacy)
    logger.info(
        "Dispatching AI: conv_id=%d user_id=%d mode=%s doc_id=%s",
        conversation_id, current_user.id, conv.mode.value,
        conv.document_id,
    )
    try:
        answer, provider, sources = _dispatch_ai(
            conversation= conv,
            message=      user_text,
            user=         current_user,
            db=           db,
        )
    except Exception as exc:
        # Roll back the user message flush — do NOT commit a hanging user msg
        db.rollback()
        logger.error(
            "AI dispatch failed: conv_id=%d user_id=%d error=%s",
            conversation_id, current_user.id, type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "I encountered an error while processing your request. "
                "Please try again. If the problem persists, check your "
                "document is fully processed or contact support."
            ),
        )

    # ── 4. Save assistant message ────────────────────────────────────────────
    assistant_msg = ChatMessage(
        conversation_id= conversation_id,
        role=            MessageRole.ASSISTANT,
        content=         answer,
        model_used=      provider,
        sources_json=    json.dumps(sources) if sources else None,
    )
    db.add(assistant_msg)

    # ── 5. Update conversation activity timestamp ────────────────────────────
    conv.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)
    db.refresh(conv)

    return SendMessageResponse(
        user_message=      _message_to_schema(user_msg),
        assistant_message= _message_to_schema(assistant_msg),
        conversation=      ConversationResponse.model_validate(conv),
    )

