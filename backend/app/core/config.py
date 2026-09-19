import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Secure AI Assistant for Legal Data Analysis"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # Database
    DATABASE_URL: str = "sqlite:///./data/secure_legal.db"

    # JWT Authentication Security
    # REQUIRED: set a strong random secret in .env — never leave the default in production.
    # Generate with: python -c "import secrets; print(secrets.token_hex(48))"
    JWT_SECRET_KEY: str = "CHANGE_ME_use_a_strong_random_secret_in_dot_env"
    ALGORITHM: str = "HS256"
    # 30 minutes recommended for production. Use 1440 only for development.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Session revocation (Phase 4)
    # When True every request validates the jti against the user_sessions table.
    # Set to False only for load testing — disables server-side logout.
    REVOCATION_ENABLED: bool = True

    # Small Language Model (SLM) Layer Settings
    MODEL_NAME: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    MAX_NEW_TOKENS: int = 512
    TEMPERATURE: float = 0.1
    DEVICE: str = "cpu"

    # Fine-Tuning & Adapter Selection Config
    USE_FINETUNED_MODEL: bool = False
    ADAPTER_PATH: str = "training/checkpoints/best_adapter"

    # Google Gemini API Config
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash"

    # Gemini API-key encryption
    # REQUIRED for production: generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If empty, the system falls back to deriving the key from JWT_SECRET_KEY (dev only).
    # NEVER share or commit this value.
    GEMINI_ENCRYPTION_KEY: str = ""

    # RAG Pipeline Configuration
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 150
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.35
    RAG_MAX_CONTEXT_CHUNKS: int = 5

    # Persistent Chat Configuration
    CHAT_MAX_HISTORY_MESSAGES: int = 20   # most-recent turns sent as context
    CHAT_MAX_HISTORY_CHARS: int = 8000    # hard char cap on the history block

    # File Upload Limits
    MAX_DOCUMENT_SIZE_MB: float = 10.0    # legal document upload limit
    MAX_VERIFICATION_SIZE_MB: float = 10.0  # credential image/PDF upload limit

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    # Per-endpoint limits (requests / window) — override in .env if needed
    RATE_LIMIT_LOGIN:          str = "5/minute"
    RATE_LIMIT_REGISTER:       str = "10/minute"
    RATE_LIMIT_PUBLIC_QUERY:   str = "20/minute"
    RATE_LIMIT_RAG_QUERY:      str = "10/minute"
    RATE_LIMIT_DOC_UPLOAD:     str = "5/minute"
    RATE_LIMIT_DOC_ANALYSIS:   str = "5/minute"
    RATE_LIMIT_CHAT_MESSAGE:   str = "20/minute"
    RATE_LIMIT_CHAT_CREATE:    str = "20/minute"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
