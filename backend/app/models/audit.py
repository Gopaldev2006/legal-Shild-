from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from app.db.base import Base


class RAGAuditLog(Base):
    """
    Audit Log ORM Model.
    Records RAG query executions, provider used, chunks retrieved, and safety status
    for compliance and security auditing by verified legal professionals and admins.
    """
    __tablename__ = "rag_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    provider_used = Column(String(255), nullable=False)
    chunks_retrieved = Column(Integer, default=0, nullable=False)
    is_safe = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
