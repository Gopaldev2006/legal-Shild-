"""
security.py — Authentication & Cryptography
============================================
Provides:
  - bcrypt password hashing / verification
  - Fernet-based API key encryption / decryption
  - JWT access token creation and validation (with jti for revocation)
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

import jwt
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from passlib.context import CryptContext

from app.core.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Return a secure bcrypt hash for a plain text password."""
    return pwd_context.hash(password)


# ── Fernet API-key encryption ─────────────────────────────────────────────────

def _get_encryption_key() -> bytes:
    """
    Return a 32-byte Fernet encryption key for Gemini API-key storage.

    Key resolution order
    --------------------
    1. ``GEMINI_ENCRYPTION_KEY`` env var — a pre-generated Fernet key
       (recommended for production).
       Generate with:
         python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    2. Derivation fallback: PBKDF2-HMAC-SHA256 over ``JWT_SECRET_KEY`` with a
       static salt (development only).  Changing JWT_SECRET_KEY will invalidate
       all stored encrypted keys when this fallback is used.

    The static-salt fallback is intentionally kept for backward-compatibility
    with existing encrypted rows in development databases.
    """
    raw = settings.GEMINI_ENCRYPTION_KEY.strip()
    if raw:
        # Use the dedicated Fernet key directly — it is already URL-safe base64
        return raw.encode()

    # Fallback: derive from JWT secret (dev / migration path)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"secure-legal-ai-salt",
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(settings.JWT_SECRET_KEY.encode()))


def encrypt_api_key(api_key: str) -> str:
    """Encrypt a Gemini API key for at-rest storage. Returns base64 ciphertext."""
    if not api_key:
        return ""
    return Fernet(_get_encryption_key()).encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> Optional[str]:
    """Decrypt a stored Gemini API key. Returns None if decryption fails."""
    if not encrypted_key:
        return None
    try:
        return Fernet(_get_encryption_key()).decrypt(encrypted_key.encode()).decode()
    except Exception:
        return None


# ── JWT access tokens ─────────────────────────────────────────────────────────

def create_access_token(
    subject: Any,
    claims:  Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str]:
    """
    Create a signed JWT access token.

    Changes from previous version:
      - A unique `jti` (JWT ID) is embedded in every token.
      - The function now returns (encoded_jwt, jti) so the caller
        can store the jti in UserSession for revocation tracking.

    Parameters
    ----------
    subject       : user_id (stored as str in the 'sub' claim)
    claims        : extra claims (e.g. email, role) — NO secrets
    expires_delta : override default expiry

    Returns
    -------
    (jwt_string, jti_string)
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    jti = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "jti": jti,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expire.timestamp()),
    }

    if claims:
        # Only allow safe, non-reserved claims — never forward secrets
        _BLOCKED = {"sub", "jti", "iat", "exp", "password", "api_key",
                    "secret", "token", "key", "hash", "encrypted"}
        for k, v in claims.items():
            if k.lower() not in _BLOCKED:
                payload[k] = v

    encoded = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded, jti


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.

    Returns the full payload dict (including 'jti') if valid, or None.
    Callers must check the 'jti' against the UserSession table to verify
    the session has not been revoked.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.PyJWTError:
        return None
