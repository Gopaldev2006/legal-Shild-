from typing import List, Optional
from pydantic import BaseModel, Field


class CaseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Legal text or query to search similar cases")
    jurisdiction: Optional[str] = Field(None, description="Optional jurisdiction filter")
    court: Optional[str] = Field(None, description="Optional court filter")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Top-k similar cases to retrieve")


class CaseSearchResultItem(BaseModel):
    case_id: str
    title: str
    court: str
    date: str
    jurisdiction: str
    similarity_score: float
    relevant_facts: str
    legal_issues: str
    arguments: str
    decision: str
    source: str
    source_reference: str


class CaseSearchResponse(BaseModel):
    results: List[CaseSearchResultItem]
    total: int


class CaseDetailResponse(BaseModel):
    case_id: str
    title: str
    court: str
    date: str
    jurisdiction: str
    facts: str
    legal_issues: str
    arguments: str
    decision: str
    source: str
    source_reference: str


class ClusterGenerateRequest(BaseModel):
    num_clusters: Optional[int] = Field(3, ge=1, le=10, description="Number of K-Means clusters to generate")


class ClusterItem(BaseModel):
    cluster_id: int
    case_count: int
    topics: List[str]
    representative_cases: List[str]
    disclaimer: str


class ClusterGenerateResponse(BaseModel):
    status: str
    clusters_generated: int
    total_cases_clustered: int
    disclaimer: str
    clusters: List[ClusterItem]


class ClusterDetailResponse(BaseModel):
    cluster_id: int
    case_count: int
    topics: List[str]
    cases: List[CaseSearchResultItem]
    disclaimer: str
