"""
permissions.py — Centralized Role-Based Access Control
=======================================================
Single source of truth for the LexGuard AI access matrix.

Role hierarchy
--------------
  PUBLIC_USER          General legal Q&A only. No documents. No RAG.
  LEGAL_PROFESSIONAL   Full document/RAG/chat pipeline.  Must be VERIFIED.
  ADMIN                Full access including user management.

Usage in routers
----------------
  from fastapi import Depends
  from app.core.permissions import require_professional, require_admin

  @router.post("/upload")
  def upload(current_user = Depends(require_professional)):
      ...

Access matrix (enforced server-side — never rely on frontend hiding)
---------------------------------------------------------------------
  Endpoint class              PUBLIC   PROFESSIONAL   ADMIN
  ─────────────────────────────────────────────────────────
  Public AI Q&A               ✓        ✓              ✓
  Own profile / sessions      ✓*       ✓              ✓
  Verification submit         ✓*       ✓              ✓
  Document upload/manage      ✗        ✓              ✓
  Document analysis           ✗        ✓              ✓
  RAG query / search          ✗        ✓              ✓
  Chat (general mode)         ✓*       ✓              ✓
  Chat (document/rag mode)    ✗        ✓              ✓
  Vector search               ✗        ✓              ✓
  Case search / clustering    ✗        ✓              ✓
  Admin dashboard             ✗        ✗              ✓
  System metrics              ✓*       ✓              ✓

  * = requires valid JWT (authenticated), not necessarily a professional

Resource ownership rules (applies on top of role checks)
---------------------------------------------------------
  Every user-owned resource enforces:
    current_user.id == resource.owner_id / user_id

  Resources:  LegalDocument, DocumentChunk, Conversation,
              ChatMessage, UserSession, VerificationRequest
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User, UserRole, VerificationStatus


# ─────────────────────────────────────────────────────────────────────────────
# Role constants (mirrors UserRole enum values)
# ─────────────────────────────────────────────────────────────────────────────

ROLE_PUBLIC       = UserRole.PUBLIC_USER
ROLE_PROFESSIONAL = UserRole.LEGAL_PROFESSIONAL
ROLE_ADMIN        = UserRole.ADMIN


# ─────────────────────────────────────────────────────────────────────────────
# Convenience dependency functions
# ─────────────────────────────────────────────────────────────────────────────

def require_authenticated(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Any valid JWT — PUBLIC, PROFESSIONAL, or ADMIN.
    Raises 401 if the token is missing/invalid/revoked (handled in get_current_user).
    """
    return current_user


def require_professional(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require LEGAL_PROFESSIONAL (VERIFIED) or ADMIN.

    Raises:
        HTTP 403 — if user is PUBLIC_USER
        HTTP 403 — if user is LEGAL_PROFESSIONAL but not VERIFIED yet
    """
    if current_user.role == ROLE_PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This feature requires a Verified Legal Professional account. "
                "Public users do not have access to document or RAG features."
            ),
        )
    if current_user.role == ROLE_PROFESSIONAL:
        if current_user.verification_status != VerificationStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your account is pending verification. "
                    "Professional features are unlocked after admin approval."
                ),
            )
    # ADMIN passes unconditionally
    return current_user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require ADMIN role.

    Raises:
        HTTP 403 — for PUBLIC_USER or LEGAL_PROFESSIONAL
    """
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is restricted to system administrators.",
        )
    return current_user


def require_professional_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Alias kept for readability — identical to require_professional."""
    return require_professional(current_user)


# ─────────────────────────────────────────────────────────────────────────────
# Ownership helpers  (call inside endpoint body, not as Depends)
# ─────────────────────────────────────────────────────────────────────────────

def assert_owner_or_admin(
    resource_owner_id: int,
    current_user: User,
    resource_name: str = "resource",
) -> None:
    """
    Raise HTTP 403 if the current user does not own the resource
    and is not an admin.

    Use after loading the resource from DB so the ownership check
    is always based on actual DB state, not request parameters.

    Parameters
    ----------
    resource_owner_id : the user_id / owner_id column value from the DB row
    current_user      : the authenticated user from get_current_user
    resource_name     : human label used in the error message

    Raises
    ------
    HTTP 403 if ownership check fails.
    """
    if current_user.role == ROLE_ADMIN:
        return  # Admin bypasses ownership check
    if resource_owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: you do not have access to this {resource_name}.",
        )


def assert_resource_exists_and_owned(
    resource,
    current_user: User,
    resource_name: str = "resource",
) -> None:
    """
    Raise HTTP 404 if resource is None (not found OR wrong owner leak prevention).
    Raise HTTP 403 if resource exists but belongs to a different user.

    This helper returns 404 first so callers never learn whether a
    resource exists for a different user.

    Parameters
    ----------
    resource     : ORM object or None
    current_user : authenticated user
    resource_name: human label for error messages
    """
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name.capitalize()} not found.",
        )
    owner_id = getattr(resource, "owner_id", getattr(resource, "user_id", None))
    if owner_id is not None and current_user.role != ROLE_ADMIN:
        if owner_id != current_user.id:
            # Return 404 not 403 — do not reveal the resource exists
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_name.capitalize()} not found.",
            )
