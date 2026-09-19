from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Legal query text")
    matter_id: Optional[str] = Field(None, description="Optional matter ID filter")
    provider_type: Optional[str] = Field("local", description="Model provider ('local' or 'external')")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Top-k vector chunks to retrieve")


class CitationItem(BaseModel):
    citation_index: int
    document_id: Optional[int] = None
    chunk_id: Optional[str] = None
    page_number: Optional[int] = 1
    matter_id: Optional[str] = None
    owner_id: Optional[int] = None
    source_type: Optional[str] = "document"
    document_type: Optional[str] = "legal_doc"
    snippet: str
    score: Optional[float] = 0.0


class RAGQueryResponse(BaseModel):
    answer: str
    citations: List[CitationItem]
    provider_used: str
    chunks_retrieved: int
    is_safe: bool
    security_report: Dict[str, Any]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    query_text: str
    provider_used: str
    chunks_retrieved: int
    is_safe: bool
    created_at: datetime


class LegalArgumentsResponse(BaseModel):
    document_id: int
    filename: str
    cited_statutes: List[str]
    key_arguments: List[str]
    verdict_summary: str


# ── Phase 3: Semantic Search schemas ─────────────────────────────────────────

class SemanticSearchRequest(BaseModel):
    query:       str            = Field(..., min_length=1, max_length=1000,
                                        description="Natural-language legal query")
    document_id: Optional[int]  = Field(None,
                                        description="Restrict search to a specific document (optional)")
    top_k:       Optional[int]  = Field(None, ge=1, le=20,
                                        description="Number of results to return (default: RAG_TOP_K=5)")


class SearchResultItem(BaseModel):
    chunk_id:     str
    document_id:  int
    chunk_index:  int
    page_number:  Optional[int]
    content:      str
    similarity:   float
    filename:     str
    matter_id:    Optional[str] = None
    jurisdiction: Optional[str] = None


class SemanticSearchResponse(BaseModel):
    query:              str
    document_id_filter: Optional[int]
    top_k:              int
    threshold:          float
    total_candidates:   int
    results:            List[SearchResultItem]
    no_relevant_context: bool


# ── Phase 4: RAG Answer schemas ───────────────────────────────────────────────

class RAGAnswerRequest(BaseModel):
    query:       str           = Field(..., min_length=1, max_length=1000,
                                       description="Legal question to answer from documents")
    document_id: Optional[int] = Field(None,
                                       description="Restrict RAG to a specific document (optional)")
    top_k:       Optional[int] = Field(None, ge=1, le=20,
                                       description="Max chunks to retrieve (default: RAG_TOP_K=5)")


class RAGSourceItem(BaseModel):
    chunk_id:     str
    document_id:  int
    filename:     str
    page_number:  Optional[int] = None
    similarity:   float
    matter_id:    Optional[str] = None
    jurisdiction: Optional[str] = None


class RAGAnswerResponse(BaseModel):
    answer:              str
    sources:             List[RAGSourceItem]
    used_rag:            bool
    provider_used:       str
    chunks_retrieved:    int
    no_relevant_context: bool
