"""
limiter.py — Shared SlowAPI Rate Limiter
=========================================
Single source-of-truth for the SlowAPI Limiter instance used across all
API routers.

Key identification strategy:
  - Authenticated requests  → keyed by user_id extracted from the JWT
                              (prevents shared-IP bypass at a proxy/NAT)
  - Unauthenticated requests → keyed by client IP address
                              (login, register, public-query)

Storage:
  - In-memory (default).  Counters reset on server restart.
  - For multi-worker / production: swap the storage URI for a Redis URL.
    Example:  Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379/0")

Usage in a router:
    from fastapi import Request
    from app.core.limiter import limiter

    @router.post("/login")
    @limiter.limit("5/minute")
    def login(request: Request, ...):   # Request MUST be a positional param
        ...
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


def _user_or_ip(request) -> str:  # type: ignore[no-untyped-def]
    """
    Key function for authenticated endpoints.

    Attempts to extract user_id from the decoded JWT stored in
    request.state (populated by FastAPI dependencies).  Falls back to
    client IP address for unauthenticated or pre-auth requests.
    """
    # FastAPI stores the resolved user on request.state when
    # get_current_user dependency has already run (AFTER the decorator).
    # For auth endpoints (login/register) the user is not yet set, so
    # we fall back to IP — which is the right behaviour there.
    user = getattr(request.state, "current_user", None)
    if user and hasattr(user, "id"):
        return f"user:{user.id}"
    return get_remote_address(request)


# ── Shared limiter instance ───────────────────────────────────────────────────
# Use get_remote_address as the default key_func for unauthenticated routes.
# Authenticated routes import _user_or_ip and pass it explicitly.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # No blanket default — we set per-endpoint limits
    headers_enabled=True,       # Adds X-RateLimit-* headers to every response
    swallow_errors=True,        # Never crash the app due to limiter storage errors
)
