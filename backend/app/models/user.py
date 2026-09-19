import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, DateTime, Text
from app.db.base import Base


class UserRole(str, enum.Enum):
    PUBLIC_USER = "PUBLIC_USER"
    LEGAL_PROFESSIONAL = "LEGAL_PROFESSIONAL"
    ADMIN = "ADMIN"


class VerificationStatus(str, enum.Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.PUBLIC_USER, nullable=False)
    verification_status = Column(
        SQLEnum(VerificationStatus), 
        default=VerificationStatus.NOT_REQUIRED, 
        nullable=False
    )
    # Encrypted Gemini API key for user's personal use
    encrypted_gemini_api_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
