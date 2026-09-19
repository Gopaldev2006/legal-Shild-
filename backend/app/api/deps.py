"""
deps.py — FastAPI dependency functions
========================================
All protected endpoints depend on get_current_user which:
  1. Decodes and validates the JWT signature + expiry.
  2. Extracts jti and checks the UserSession table for revocation
     (when REVOCATION_ENABLED=True).
  3. Loads the User from the database — confirms the account still exists.
  4. Returns the User ORM object for downstream use.

This gives proper logout / revoke-session semantics: a revoked token is
rejected even if it hasn't expired yet.
"""

from typing import Generator, List, Optional
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User, UserRole, VerificationStatus
from app.models.session import UserSession
from app.core.security import decode_access_token, decrypt_api_key
from app.core.config import settings

security = HTTPBearer()


# ── Database session ──────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """Yield a database session, close it when the request ends."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Core auth dependency ──────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate Bearer token and return the authenticated User.

    Validation chain:
      1. Decode JWT signature + expiry.
      2. Extract user_id from 'sub' claim.
      3. If REVOCATION_ENABLED: look up the jti in user_sessions.
         Reject if revoked or not found.
      4. Load User from DB — rejects if account was deleted.
      5. Update session.last_used_at (best-effort, never blocks the request).

    Raises HTTP 401 for any failure.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Extract user_id ───────────────────────────────────────────────────────
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── JTI revocation check ──────────────────────────────────────────────────
    if settings.REVOCATION_ENABLED:
        jti = payload.get("jti")
        if not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required identifier (jti)",
                headers={"WWW-Authenticate": "Bearer"},
            )

        session = db.query(UserSession).filter(UserSession.jti == jti).first()

        if session is None:
            # Token was never registered (pre-Phase 4 token or forged token)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if session.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This session has been revoked. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Best-effort: update last_used_at without blocking on failure
        try:
            session.last_used_at = datetime.now(timezone.utc)
            db.add(session)
            db.commit()
        except Exception:
            db.rollback()

    # ── Load user from DB ─────────────────────────────────────────────────────
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ── Optional auth (public endpoints that accept both auth'd and anon) ─────────

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional authentication — returns User if token is valid, None otherwise.
    Does not raise for missing or invalid tokens.
    """
    if not credentials:
        return None
    try:
        return get_current_user.__wrapped__(credentials, db)
    except Exception:
        pass

    # Manual fallback — decode without revocation for optional paths
    try:
        payload = decode_access_token(credentials.credentials)
        if not payload or "sub" not in payload:
            return None
        user_id = int(payload["sub"])
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


# ── Gemini API key helpers ────────────────────────────────────────────────────

def get_user_gemini_api_key(
    current_user: User = Depends(get_current_user),
) -> Optional[str]:
    """Return decrypted Gemini API key for the current authenticated user."""
    if not current_user.encrypted_gemini_api_key:
        return None
    return decrypt_api_key(current_user.encrypted_gemini_api_key)


def get_user_gemini_api_key_optional(
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Optional[str]:
    """Return decrypted Gemini API key, or None for anonymous users."""
    if not current_user or not current_user.encrypted_gemini_api_key:
        return None
    return decrypt_api_key(current_user.encrypted_gemini_api_key)


# ── RBAC helpers ──────────────────────────────────────────────────────────────

def require_roles(*allowed_roles: UserRole):
    """
    Dependency factory: enforce role-based access control.
    Raises HTTP 403 if current user's role is not in allowed_roles.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission denied. "
                    f"Required role: {', '.join(r.value for r in allowed_roles)}"
                ),
            )
        return current_user
    return role_checker


def require_verified_legal_professional(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require LEGAL_PROFESSIONAL (verified) or ADMIN.
    Unverified professionals are rejected with HTTP 403.
    """
    if current_user.role == UserRole.PUBLIC_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Public users cannot access the Secure RAG pipeline.",
        )
    if current_user.role == UserRole.LEGAL_PROFESSIONAL:
        if current_user.verification_status != VerificationStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Permission denied. "
                    "Professional verification (VERIFIED status) is required."
                ),
            )
    return current_user
