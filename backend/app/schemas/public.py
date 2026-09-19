from typing import Optional
from pydantic import BaseModel, Field


class PublicQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="General legal question or term explanation query")


class PublicQueryResponse(BaseModel):
    answer: str
    disclaimer: str
    is_safe: bool
    topic: Optional[str] = "General Educational Information"
