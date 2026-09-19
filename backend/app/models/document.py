import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, Enum as SQLEnum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class ProcessingStatus(str, enum.Enum):
    UPLOADING  = "UPLOADING"
    PROCESSING = "PROCESSING"
    CHUNKING   = "CHUNKING"
    EMBEDDED   = "EMBEDDED"
    READY      = "READY"
    COMPLETED  = "COMPLETED"   # kept for backward-compat
    FAILED     = "FAILED"


class DocumentType(str, enum.Enum):
    CASE_BRIEF  = "case_brief"
    STATUTE     = "statute"
    COURT_ORDER = "court_order"
    CONTRACT    = "contract"
    GENERAL     = "general"


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id               = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename         = Column(String(255), nullable=False)
    stored_filename  = Column(String(255), nullable=False)
    stored_path      = Column(String(500), nullable=False)
    file_type        = Column(String(10),  nullable=False)   # pdf, docx, txt
    file_size        = Column(Integer,     nullable=False)   # bytes
    file_hash        = Column(String(64),  nullable=False)   # SHA-256
    document_type    = Column(SQLEnum(DocumentType),    default=DocumentType.GENERAL,      nullable=False)
    jurisdiction     = Column(String(100), nullable=True)
    matter_id        = Column(String(100), nullable=True)
    processing_status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.UPLOADING, nullable=False)
    error_message    = Column(Text, nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at       = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner  = relationship("User", foreign_keys=[owner_id])
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """
    Stores an individual text chunk extracted from a LegalDocument.
    Designed as the atomic unit for Phase 2 embedding & vector search.

    Ownership chain:  User → LegalDocument → DocumentChunk
    Authorization always validates: chunk.owner_id == current_user.id
    """
    __tablename__ = "document_chunks"

    id              = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chunk_id        = Column(String(100), unique=True, index=True, nullable=False)   # deterministic UUID
    document_id     = Column(Integer, ForeignKey("legal_documents.id"), nullable=False, index=True)
    owner_id        = Column(Integer, ForeignKey("users.id"),           nullable=False, index=True)
    matter_id       = Column(String(100), nullable=True)

    # ── content ───────────────────────────────────────────────────────────────
    text            = Column(Text,    nullable=False)
    page_number     = Column(Integer, nullable=True)
    chunk_index     = Column(Integer, nullable=False)

    # ── character offsets (relative to the full document text) ────────────────
    start_char      = Column(Integer, nullable=True)   # inclusive start offset
    end_char        = Column(Integer, nullable=True)   # exclusive end offset

    # ── token estimate (≈ len(text) / 4 — good enough for Phase 1) ───────────
    token_count     = Column(Integer, nullable=True)

    # ── serialised JSON metadata (filename, doc_type, jurisdiction …) ─────────
    source_metadata = Column(Text, nullable=True)

    # ── embedding (Phase 2) ───────────────────────────────────────────────────
    # Stored as a raw IEEE-754 float32 binary blob (numpy .tobytes()).
    # Format:  numpy.frombuffer(embedding, dtype=numpy.float32)
    # Dimension: 384 for all-MiniLM-L6-v2
    embedding       = Column(Text, nullable=True)    # base64-encoded float32 bytes
    embedding_dim   = Column(Integer, nullable=True) # e.g. 384
    is_embedded     = Column(Boolean, default=False, nullable=False)

    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    document = relationship("LegalDocument", back_populates="chunks")
    owner    = relationship("User", foreign_keys=[owner_id])
