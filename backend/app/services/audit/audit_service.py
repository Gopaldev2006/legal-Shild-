"""
audit_service.py — Security Audit Event Writer
===============================================
Central helper used by all API routers to record audit events.

Usage
-----
    from app.services.audit.audit_service import write_audit_event
    from app.models.audit_log import AuditEventType

    # Inside an endpoint (synchronous):
    write_audit_event(
        db=db,
        event_type=AuditEventType.LOGIN_SUCCESS,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        success=True,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"role": user.role.value},
    )

Security rules enforced here
-----------------------------
  • metadata dict is sanitised before storage:
    keys named 'password', 'token', 'key', 'secret', 'hash', 'credential'
    are silently removed so callers cannot accidentally log secrets.
  • write_audit_event NEVER raises — any DB error is swallowed and
    logged to the Python logger so an audit write failure never
    breaks the actual request flow.
  • Rows are INSERT-only; no UPDATE or DELETE ever touches this table.
"""

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog, AuditEventType

logger = logging.getLogger(__name__)

# Keys that must never appear in audit metadata (case-insensitive substring match)
_BLOCKED_META_KEYS = frozenset({
    "password", "passwd", "token", "access_token", "refresh_token",
    "api_key", "apikey", "secret", "key", "hash", "credential",
    "encrypted", "private", "authorization",
})


def _sanitise_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Remove any key whose name contains a blocked substring, then JSON-serialise.
    Returns None if the dict is empty or None.
    """
    if not metadata:
        return None

    clean: Dict[str, Any] = {}
    for k, v in metadata.items():
        k_lower = k.lower()
        if any(blocked in k_lower for blocked in _BLOCKED_META_KEYS):
            continue  # silently drop — never log secrets
        # Truncate long string values so metadata stays compact
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + "…"
        clean[k] = v

    if not clean:
        return None

    try:
        return json.dumps(clean, default=str)
    except Exception:
        return None


def write_audit_event(
    db:            Session,
    event_type:    AuditEventType,
    *,
    user_id:       Optional[int]            = None,
    resource_type: Optional[str]            = None,
    resource_id:   Optional[int]            = None,
    success:       bool                     = True,
    ip_address:    Optional[str]            = None,
    user_agent:    Optional[str]            = None,
    metadata:      Optional[Dict[str, Any]] = None,
) -> None:
    """
    Insert one audit log row. Never raises — failures are logged only.

    Parameters
    ----------
    db            : active SQLAlchemy session
    event_type    : AuditEventType enum value
    user_id       : authenticated user's id (None for pre-auth failures)
    resource_type : "document" | "chat" | "session" | "user" | etc.
    resource_id   : numeric DB id of the affected resource
    success       : True for normal completion; False for blocked/failed events
    ip_address    : client IP (from request.client.host — never X-Forwarded-For)
    user_agent    : browser/client identifier (truncated to 200 chars)
    metadata      : small safe dict — secrets automatically stripped
    """
    try:
        entry = AuditLog(
            event_type=    event_type,
            user_id=       user_id,
            resource_type= resource_type,
            resource_id=   resource_id,
            success=       success,
            ip_address=    ip_address,
            user_agent=    (user_agent or "")[:200] or None,
            metadata_json= _sanitise_metadata(metadata),
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        # Audit write must NEVER break the caller's request
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "Audit write failed: event=%s user=%s error=%s",
            event_type.value, user_id, type(exc).__name__,
        )
