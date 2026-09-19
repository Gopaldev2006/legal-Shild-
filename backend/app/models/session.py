"""
session.py — UserSession model for JWT revocation tracking
===========================================================
Every successful login creates one UserSession row.
The `jti` (JWT ID) stored here is compared against incoming tokens.
If `revoked_at` is set, the token is rejected — even if its signature
and expiry are still valid.

This gives us proper logout and revoke-all-sessions semantics without
forcing very short token lifetimes as the only protection.

Security design:
  - We store only the jti (UUID), never the raw JWT string.
  - Revocation check is a single indexed DB read per request.
  - The table is append-only in the sense that rows are never deleted;
    revocation is a soft update (sets revoked_at).
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserSession(Base):
    """
    Tracks one login session per row.

    Fields
    ------
    jti          : JWT ID claim — unique per token; stored as string UUID.
                   This is the primary revocation handle.
    user_id      : FK to users table.
    created_at   : When the login occurred / session was created.
    expires_at   : Mirrors the JWT exp claim so we can clean up stale rows.
    last_used_at : Updated on every authenticated request (best-effort).
    revoked_at   : Set when the session is explicitly revoked. NULL = active.
    ip_address   : Client IP at login time (metadata only, never used for auth).
    user_agent   : Browser/client user-agent at login time (metadata only).
    """

    __tablename__ = "user_sessions"

    id           = Column(Integer, primary_key=True, autoincrement=True)

    # JWT ID — the unique identifier embedded in the token
    jti          = Column(String(64), unique=True, nullable=False, index=True)

    # Owning user
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Timestamps
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at   = Column(DateTime, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at   = Column(DateTime, nullable=True)   # NULL = active session

    # Client metadata (stored for display, never used for authorisation)
    ip_address   = Column(String(45), nullable=True)   # IPv4 or IPv6
    user_agent   = Column(Text,       nullable=True)

    # Relationship (lazy load to avoid N+1 on every auth check)
    owner = relationship("User", foreign_keys=[user_id])

    # ── Composite indexes ────────────────────────────────────────────────────
    __table_args__ = (
        # Revocation check: WHERE jti = ? AND revoked_at IS NULL
        Index("idx_session_jti_active", "jti", "revoked_at"),
        # User's session list: WHERE user_id = ? ORDER BY created_at DESC
        Index("idx_session_user_created", "user_id", "created_at"),
    )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        """True if not revoked and not expired."""
        if self.revoked_at is not None:
            return False
        now = datetime.now(timezone.utc)
        exp = self.expires_at
        # Make exp timezone-aware if stored as naive UTC
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now < exp

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return "revoked"
        now = datetime.now(timezone.utc)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now >= exp:
            return "expired"
        return "active"
