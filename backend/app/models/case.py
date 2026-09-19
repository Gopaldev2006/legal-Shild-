from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.base import Base


class LegalCase(Base):
    """
    Legal Case ORM Model.
    Represents public academic legal cases, court judgments, precedent decisions,
    legal issues, arguments, verdicts, and cluster assignment.
    """
    __tablename__ = "legal_cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    court = Column(String(255), nullable=False)
    date = Column(String(100), nullable=True, default="Not available in the indexed source.")
    jurisdiction = Column(String(100), nullable=True, default="Not available in the indexed source.")
    facts = Column(Text, nullable=True, default="Not available in the indexed source.")
    legal_issues = Column(Text, nullable=True, default="Not available in the indexed source.")
    arguments = Column(Text, nullable=True, default="Not available in the indexed source.")
    decision = Column(Text, nullable=True, default="Not available in the indexed source.")
    source = Column(String(255), nullable=True, default="Public Academic Legal Case Repository")
    source_reference = Column(String(255), nullable=True, default="Not available in the indexed source.")
    cluster_id = Column(Integer, nullable=True, default=None, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
