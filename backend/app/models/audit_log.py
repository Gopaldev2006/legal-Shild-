"""
audit_log.py — Security Audit Log Model
=========================================
Append-only security accountability records.

Design rules:
  • NEVER store passwords, tokens, API keys, encryption keys,
    complete document text, or complete conversation content.
  • Record WHAT happened (event type, who, which resource, success/failure).
  • metadata_json may store small, safe context (filename, doc_id, provider)
    but never sensitive values.
  • Rows are never updated or deleted by the application — append-only.
  • Only ADMIN role can read these records via the API.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, Enum as SQLEnum, Index,
)
from app.db.base import Base


class AuditEventType(str, enum.Enum):
    # ── Authentication ────────────────────────────────────────────────────────
    LOGIN_SUCCESS        = "LOGIN_SUCCESS"
    LOGIN_FAILURE        = "LOGIN_FAILURE"
    LOGOUT               = "LOGOUT"
    REGISTER             = "REGISTER"
    SESSION_REVOKED      = "SESSION_REVOKED"
    SESSION_REVOKE_ALL   = "SESSION_REVOKE_ALL"

    # ── Document lifecycle ────────────────────────────────────────────────────
    DOCUMENT_UPLOADED    = "DOCUMENT_UPLOADED"
    DOCUMENT_ACCESSED    = "DOCUMENT_ACCESSED"
    DOCUMENT_ANALYZED    = "DOCUMENT_ANALYZED"
    DOCUMENT_DELETED     = "DOCUMENT_DELETED"
    DOCUMENT_REPROCESSED = "DOCUMENT_REPROCESSED"

    # ── AI / RAG ──────────────────────────────────────────────────────────────
    RAG_QUERY            = "RAG_QUERY"
    RAG_ACCESS_DENIED    = "RAG_ACCESS_DENIED"

    # ── Chat ──────────────────────────────────────────────────────────────────
    CHAT_CREATED         = "CHAT_CREATED"
    CHAT_DELETED         = "CHAT_DELETED"

    # ── API key management ────────────────────────────────────────────────────
    API_KEY_ADDED        = "API_KEY_ADDED"
    API_KEY_REMOVED      = "API_KEY_REMOVED"

    # ── Access control ────────────────────────────────────────────────────────
    ACCESS_DENIED        = "ACCESS_DENIED"
    RATE_LIMIT_EXCEEDED  = "RATE_LIMIT_EXCEEDED"

    # ── Admin actions ─────────────────────────────────────────────────────────
    ADMIN_ACTION         = "ADMIN_ACTION"
    VERIFICATION_APPROVED = "VERIFICATION_APPROVED"
    VERIFICATION_REJECTED = "VERIFICATION_REJECTED"


class AuditLog(Base):
    """
    Immutable security audit record.

    One row per significant security or accountability event.
    The application never updates or deletes these rows.

    Columns
    -------
    user_id       : FK to users table (nullable — anonymous/pre-auth events)
    event_type    : AuditEventType enum value
    resource_type : human-readable resource category ("document", "chat", "session")
    resource_id   : numeric ID of the affected resource (nullable)
    success       : True = event completed normally; False = blocked/failed
    ip_address    : client IP at the time of the event (metadata only)
    user_agent    : browser/client identifier (metadata only, truncated to 200)
    metadata_json : small JSON dict with safe context — NEVER secrets
    created_at    : UTC timestamp, immutable after insert
    """

    __tablename__ = "audit_logs"

    id            = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Who — nullable because we log LOGIN_FAILURE before we know the user
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"),
                           nullable=True, index=True)

    # What
    event_type    = Column(SQLEnum(AuditEventType), nullable=False, index=True)

    # Which resource
    resource_type = Column(String(50), nullable=True)   # "document", "chat", "session"
    resource_id   = Column(Integer,    nullable=True)   # DB row id of affected resource

    # Outcome
    success       = Column(Boolean, nullable=False, default=True)

    # Request context (metadata only, never used for auth)
    ip_address    = Column(String(45), nullable=True)
    user_agent    = Column(String(200), nullable=True)

    # Safe contextual details — NEVER put secrets here
    # Example: {"filename": "contract.pdf", "provider": "gemini", "mode": "document"}
    metadata_json = Column(Text, nullable=True)

    # Immutable timestamp
    created_at    = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("idx_audit_user_created",  "user_id",    "created_at"),
        Index("idx_audit_event_created", "event_type", "created_at"),
    )
