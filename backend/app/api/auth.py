"""
auth.py — Authentication & Session Management
==============================================
Endpoints:
  POST   /auth/register             Create new PUBLIC_USER account
  POST   /auth/login                Authenticate; issue JWT + create UserSession
  POST   /auth/logout               Revoke the current session (soft delete)
  GET    /auth/me                   Current user profile
  GET    /auth/sessions             List user's sessions (safe metadata only)
  DELETE /auth/sessions/{id}        Revoke a specific session by DB id
  POST   /auth/sessions/revoke-all  Revoke all active sessions for the user

  Gemini API key management:
  POST   /auth/gemini-api-key
  GET    /auth/gemini-api-key
  DELETE /auth/gemini-api-key
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.models.user import User, UserRole, VerificationStatus
from app.models.session import UserSession
from app.schemas.user import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    GeminiApiKeySet, GeminiApiKeyResponse, GeminiApiKeyStatus,
    SessionResponse, SessionListResponse, RevokeAllResponse,
)
from app.core.security import (
    get_password_hash, verify_password, create_access_token,
    encrypt_api_key, decrypt_api_key,
)
from app.core.limiter import limiter
from app.core.config import settings
from app.services.audit.audit_service import write_audit_event
from app.models.audit_log import AuditEventType

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _user_response(user: User) -> dict:
    return {
        "id":                   user.id,
        "name":                 user.name,
        "email":                user.email,
        "role":                 user.role,
        "verification_status":  user.verification_status,
        "has_gemini_api_key":   bool(user.encrypted_gemini_api_key),
        "created_at":           user.created_at,
        "updated_at":           user.updated_at,
    }


def _session_to_schema(s: UserSession) -> SessionResponse:
    return SessionResponse(
        id=           s.id,
        jti=          s.jti,
        created_at=   s.created_at,
        expires_at=   s.expires_at,
        last_used_at= s.last_used_at,
        revoked_at=   s.revoked_at,
        ip_address=   s.ip_address,
        user_agent=   s.user_agent,
        status=       s.status,
    )


def _client_ip(request: Request) -> Optional[str]:
    """Return the real client IP from the TCP connection (not forwarded headers)."""
    if request.client:
        return request.client.host
    return None


def _get_session_or_404(session_id: int, user_id: int, db: Session) -> UserSession:
    """Load a session by id, enforcing ownership. 404 for missing OR wrong owner."""
    s = db.query(UserSession).filter(
        UserSession.id      == session_id,
        UserSession.user_id == user_id,
    ).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
)
@limiter.limit(lambda: settings.RATE_LIMIT_REGISTER)
def register_user(
    request: Request,
    user_in: UserRegister,
    db: Session = Depends(get_db),
):
    """
    Register a new public user account.
    Role is always PUBLIC_USER — clients cannot elevate themselves at registration.
    """
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered",
        )

    new_user = User(
        name=                user_in.name.strip(),
        email=               user_in.email.lower().strip(),
        password_hash=       get_password_hash(user_in.password),
        role=                UserRole.PUBLIC_USER,
        verification_status= VerificationStatus.NOT_REQUIRED,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return _user_response(new_user)


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login & JWT Issuance",
)
@limiter.limit(lambda: settings.RATE_LIMIT_LOGIN)
def login_user(
    request: Request,
    user_in: UserLogin,
    db: Session = Depends(get_db),
):
    """
    Authenticate credentials and issue a signed JWT access token.

    A UserSession row is created for every successful login, enabling
    server-side revocation via the jti claim.
    """
    user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if not user or not verify_password(user_in.password, user.password_hash):
        # Audit: LOGIN_FAILURE — do NOT include the attempted password
        write_audit_event(
            db=db,
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id=user.id if user else None,
            resource_type="user",
            success=False,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            metadata={"email_domain": user_in.email.split("@")[-1] if "@" in user_in.email else None},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create token — returns (jwt_string, jti)
    access_token, jti = create_access_token(
        subject=user.id,
        claims={"email": user.email, "role": user.role.value},
    )

    # Calculate expiry to store in UserSession
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Persist the session record
    session = UserSession(
        jti=        jti,
        user_id=    user.id,
        expires_at= expires_at,
        ip_address= _client_ip(request),
        user_agent= request.headers.get("user-agent", "")[:500],
    )
    db.add(session)
    db.commit()

    # Audit: LOGIN_SUCCESS
    write_audit_event(
        db=db,
        event_type=AuditEventType.LOGIN_SUCCESS,
        user_id=user.id,
        resource_type="session",
        resource_id=session.id,
        success=True,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"role": user.role.value},
    )

    return {
        "access_token": access_token,
        "token_type":   "bearer",
        "user":         _user_response(user),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout — revoke the current session",
)
def logout(
    request: Request,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Revoke the JWT used in this request.

    The jti is extracted from the Authorization header and the corresponding
    UserSession row is soft-deleted (revoked_at is set). Subsequent requests
    with the same token will receive HTTP 401.
    """
    from fastapi.security import HTTPBearer
    from app.core.security import decode_access_token as _decode

    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    payload = _decode(token)

    if payload:
        jti = payload.get("jti")
        if jti:
            session = db.query(UserSession).filter(UserSession.jti == jti).first()
            if session and session.revoked_at is None:
                session.revoked_at = datetime.now(timezone.utc)
                db.add(session)
                db.commit()
                # Audit: LOGOUT
                write_audit_event(
                    db=db,
                    event_type=AuditEventType.LOGOUT,
                    user_id=current_user.id,
                    resource_type="session",
                    resource_id=session.id,
                    success=True,
                    ip_address=_client_ip(request),
                    user_agent=request.headers.get("user-agent", ""),
                )

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Current user profile
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse, summary="Get Current User Profile")
def get_me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


# ─────────────────────────────────────────────────────────────────────────────
# Session management
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List active and recent sessions",
)
def list_sessions(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Return safe session metadata for the current user.
    Never returns raw JWT strings, passwords, or API keys.
    """
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == current_user.id)
        .order_by(UserSession.created_at.desc())
        .limit(50)
        .all()
    )

    schemas      = [_session_to_schema(s) for s in sessions]
    active_count = sum(1 for s in sessions if s.is_active)

    return SessionListResponse(
        sessions=     schemas,
        total=        len(schemas),
        active_count= active_count,
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a specific session",
)
def revoke_session(
    session_id:   int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Revoke one session by its database ID.
    Only the session owner can revoke it (ownership enforced by query filter).
    """
    session = _get_session_or_404(session_id, current_user.id, db)

    if session.revoked_at is not None:
        # Already revoked — idempotent
        return None

    session.revoked_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    # Audit: SESSION_REVOKED
    write_audit_event(
        db=db, event_type=AuditEventType.SESSION_REVOKED,
        user_id=current_user.id, resource_type="session", resource_id=session_id,
        success=True,
    )
    return None


@router.post(
    "/sessions/revoke-all",
    response_model=RevokeAllResponse,
    summary="Revoke all active sessions",
)
def revoke_all_sessions(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Immediately revoke every active session for the current user.
    The token used in this request will also be revoked — the user
    must log in again on all devices.
    """
    now = datetime.now(timezone.utc)

    active_sessions = (
        db.query(UserSession)
        .filter(
            UserSession.user_id    == current_user.id,
            UserSession.revoked_at == None,   # noqa: E711
        )
        .all()
    )

    for s in active_sessions:
        s.revoked_at = now
        db.add(s)

    db.commit()

    # Audit: SESSION_REVOKE_ALL
    write_audit_event(
        db=db, event_type=AuditEventType.SESSION_REVOKE_ALL,
        user_id=current_user.id, resource_type="session",
        success=True, metadata={"revoked_count": len(active_sessions)},
    )
    return RevokeAllResponse(
        revoked_count=len(active_sessions),
        message=(
            f"Revoked {len(active_sessions)} session(s). "
            f"Please log in again on all devices."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sample protected routes (kept for testing)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/protected-sample", summary="Sample Protected Endpoint")
def protected_sample(current_user: User = Depends(get_current_user)):
    return {
        "message": "Protected route accessed successfully",
        "user_id": current_user.id,
        "role":    current_user.role.value,
    }


@router.get("/professional-only", summary="Professional Role Required")
def professional_only_endpoint(
    current_user: User = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN))
):
    return {
        "message":             "Welcome to Verified Legal Professional Workspace",
        "user_id":             current_user.id,
        "role":                current_user.role.value,
        "verification_status": current_user.verification_status.value,
    }


@router.get("/admin-only", summary="Admin Role Required")
def admin_only_endpoint(
    current_user: User = Depends(require_roles(UserRole.ADMIN))
):
    return {
        "message": "Welcome to System Admin Workspace",
        "user_id": current_user.id,
        "role":    current_user.role.value,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Gemini API key management (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/gemini-api-key", response_model=GeminiApiKeyResponse,
             summary="Set User's Gemini API Key")
def set_gemini_api_key(
    api_key_data: GeminiApiKeySet,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    current_user.encrypted_gemini_api_key = encrypt_api_key(api_key_data.api_key.strip())
    db.commit()
    db.refresh(current_user)
    preview = api_key_data.api_key[:8] + "***" if len(api_key_data.api_key) > 8 else "***"
    # Audit: API_KEY_ADDED — preview only, never the real key
    write_audit_event(
        db=db, event_type=AuditEventType.API_KEY_ADDED,
        user_id=current_user.id, resource_type="api_key", success=True,
        metadata={"preview": preview},
    )
    return {"has_api_key": True, "api_key_preview": preview,
            "message": "Gemini API key saved successfully"}


@router.get("/gemini-api-key", response_model=GeminiApiKeyStatus,
            summary="Get Gemini API Key Status")
def get_gemini_api_key_status(current_user: User = Depends(get_current_user)):
    has_key = bool(current_user.encrypted_gemini_api_key)
    preview = None
    if has_key:
        dec = decrypt_api_key(current_user.encrypted_gemini_api_key)
        if dec:
            preview = dec[:8] + "***" if len(dec) > 8 else "***"
    return {"has_api_key": has_key, "api_key_preview": preview}


@router.delete("/gemini-api-key", response_model=GeminiApiKeyResponse,
               summary="Delete User's Gemini API Key")
def delete_gemini_api_key(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    current_user.encrypted_gemini_api_key = None
    db.commit()
    # Audit: API_KEY_REMOVED
    write_audit_event(
        db=db, event_type=AuditEventType.API_KEY_REMOVED,
        user_id=current_user.id, resource_type="api_key", success=True,
    )
    return {"has_api_key": False, "api_key_preview": None,
            "message": "Gemini API key deleted successfully"}
