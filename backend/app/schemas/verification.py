from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.user import VerificationStatus


class VerificationResponse(BaseModel):
    id: int
    user_id: int
    document_hash: str
    extracted_text: Optional[str] = None
    status: VerificationStatus
    reviewer_id: Optional[int] = None
    review_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminReviewAction(BaseModel):
    review_notes: Optional[str] = None
