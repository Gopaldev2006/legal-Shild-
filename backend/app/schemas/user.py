from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.user import UserRole, VerificationStatus


class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the user")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, max_length=100, description="Secure password (min 6 characters)")

    # NOTE: Role is NOT included here, ensuring normal users CANNOT select LEGAL_PROFESSIONAL or ADMIN.


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    verification_status: VerificationStatus
    has_gemini_api_key: bool = Field(default=False, description="Whether user has configured their own Gemini API key")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


# API Key Management Schemas
class GeminiApiKeySet(BaseModel):
    api_key: str = Field(..., min_length=10, max_length=500, description="Google Gemini API key")


class GeminiApiKeyResponse(BaseModel):
    has_api_key: bool = Field(..., description="Whether user has an API key configured")
    api_key_preview: Optional[str] = Field(None, description="Masked preview of API key (first 8 chars + ***)")
    message: str


class GeminiApiKeyStatus(BaseModel):
    has_api_key: bool
    api_key_preview: Optional[str] = None


# ── Session Management Schemas (Phase 4) ──────────────────────────────────────

class SessionResponse(BaseModel):
    """Safe session metadata returned to the client. Never includes raw JWT."""
    id: int
    jti: str = Field(..., description="JWT ID — used to identify/revoke the session")
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = Field(..., description="active | expired | revoked")

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    """Paginated list of the user's sessions."""
    sessions: list[SessionResponse]
    total: int
    active_count: int


class RevokeAllResponse(BaseModel):
    revoked_count: int
    message: str
