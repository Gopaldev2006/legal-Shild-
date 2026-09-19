from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.audit import RAGAuditLog
from app.api.deps import get_db, require_verified_legal_professional, get_user_gemini_api_key_optional
from app.schemas.public import PublicQueryRequest, PublicQueryResponse
from app.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    AuditLogResponse,
    LegalArgumentsResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SearchResultItem,
    RAGAnswerRequest,
    RAGAnswerResponse,
    RAGSourceItem,
)
from app.services.vector.retrieval_service import UserContext
from app.services.rag.rag_service import rag_service
from app.services.retrieval.retrieval_service import retrieve_relevant_chunks
from app.services.rag.rag_answer_service import rag_answer
from app.core.config import settings
from app.core.limiter import limiter

router = APIRouter(prefix="/rag", tags=["Secure RAG & Two-Tier Assistant"])


@router.post("/public-query", response_model=PublicQueryResponse)
@limiter.limit(lambda: settings.RATE_LIMIT_PUBLIC_QUERY)
def run_public_legal_query(
    request: Request,
    payload: PublicQueryRequest,
    user_api_key: Optional[str] = Depends(get_user_gemini_api_key_optional)
):
    """
    TIER 1 — PUBLIC ASSISTANT ENDPOINT
    Provides general legal information, legal terms explanations, and educational responses.
    Guarantees ZERO access to private documents or vector RAG repository.
    Includes mandatory legal educational disclaimer.
    If user has configured their own Gemini API key, it will be used.
    Authentication is optional - works for both authenticated and anonymous users.
    """
    result = rag_service.process_public_query(
        query=payload.query,
        user_api_key=user_api_key
    )
    return result


@router.post("/query", response_model=RAGAnswerResponse,
             summary="Phase 4 — Grounded RAG Answer (retrieval + context + Gemini/fallback)")
@limiter.limit(lambda: settings.RATE_LIMIT_RAG_QUERY)
def run_secure_rag_query(
    request: Request,
    payload:      RAGAnswerRequest,
    current_user: User    = Depends(require_verified_legal_professional),
    db:           Session = Depends(get_db),
):
    """
    TIER 2 — PHASE 4 GROUNDED RAG ENDPOINT

    Full pipeline:
      query → embed → retrieve owner-scoped chunks → build context
      → Gemini (if valid key) OR grounded free engine
      → answer + sources

    Security
    --------
    Restricted to VERIFIED LEGAL_PROFESSIONAL or ADMIN.
    Retrieval is always scoped to current_user.id.
    Cross-user document leakage is impossible by design.
    """
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must not be empty",
        )

    result = rag_answer(
        query=       payload.query,
        user_id=     current_user.id,
        db=          db,
        document_id= payload.document_id,
        top_k=       payload.top_k,
    )

    return RAGAnswerResponse(
        answer=              result.answer,
        sources=             [
            RAGSourceItem(
                chunk_id=    s.chunk_id,
                document_id= s.document_id,
                filename=    s.filename,
                page_number= s.page_number,
                similarity=  s.similarity,
                matter_id=   s.matter_id,
                jurisdiction=s.jurisdiction,
            )
            for s in result.sources
        ],
        used_rag=            result.used_rag,
        provider_used=       result.provider_used,
        chunks_retrieved=    result.chunks_retrieved,
        no_relevant_context= result.no_relevant_context,
    )


@router.get("/audit-history", response_model=List[AuditLogResponse])
def get_rag_audit_history(
    current_user: User = Depends(require_verified_legal_professional),
    db: Session = Depends(get_db)
):
    """
    TIER 2 — VERIFIED PROFESSIONAL AUDIT HISTORY
    Returns query audit log history for current verified legal professional.
    """
    logs = db.query(RAGAuditLog).filter(
        RAGAuditLog.user_id == current_user.id
    ).order_by(RAGAuditLog.created_at.desc()).all()
    return logs


@router.post("/extract-arguments/{document_id}", response_model=LegalArgumentsResponse)
def extract_document_legal_arguments(
    document_id: int,
    current_user: User = Depends(require_verified_legal_professional),
    db: Session = Depends(get_db)
):
    """
    TIER 2 — LEGAL ARGUMENTS & VERDICT EXTRACTION
    Extracts key legal arguments, statutory provisions cited, and verdict holding
    for an authorized legal document owned by the verified professional.
    """
    result = rag_service.extract_arguments_and_verdict(
        db=db,
        document_id=document_id,
        user_id=current_user.id
    )
    return result


@router.post("/search", response_model=SemanticSearchResponse,
             summary="Semantic Search — Top-K chunk retrieval over user's documents")
@limiter.limit(lambda: settings.RATE_LIMIT_RAG_QUERY)
def semantic_search(
    request: Request,
    payload:      SemanticSearchRequest,
    current_user: User    = Depends(require_verified_legal_professional),
    db:           Session = Depends(get_db),
):
    """
    PHASE 3 — SEMANTIC RETRIEVAL ENDPOINT

    Embeds the query with the same all-MiniLM-L6-v2 model used during
    document processing, then performs cosine similarity search over
    the authenticated user's embedded chunks.

    Security
    --------
    - Requires VERIFIED LEGAL_PROFESSIONAL or ADMIN role.
    - Retrieval is scoped to current_user.id — users never see each
      other's document chunks.
    - If document_id is supplied it is also validated for ownership.

    Threshold
    ---------
    Only chunks with similarity >= RAG_SIMILARITY_THRESHOLD (0.35) are
    returned. If none qualify, no_relevant_context=True is set so the
    caller knows to surface a "no relevant content found" message.
    """
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must not be empty",
        )

    _top_k     = payload.top_k if payload.top_k is not None else settings.RAG_TOP_K
    _threshold = settings.RAG_SIMILARITY_THRESHOLD

    results = retrieve_relevant_chunks(
        query=       payload.query,
        user_id=     current_user.id,
        db=          db,
        document_id= payload.document_id,
        top_k=       _top_k,
        threshold=   _threshold,
    )

    items = [
        SearchResultItem(
            chunk_id=    r.chunk_id,
            document_id= r.document_id,
            chunk_index= r.chunk_index,
            page_number= r.page_number,
            content=     r.content,
            similarity=  r.similarity,
            filename=    r.filename,
            matter_id=   r.matter_id,
            jurisdiction=r.jurisdiction,
        )
        for r in results
    ]

    return SemanticSearchResponse(
        query=               payload.query,
        document_id_filter=  payload.document_id,
        top_k=               _top_k,
        threshold=           _threshold,
        total_candidates=    len(items),
        results=             items,
        no_relevant_context= len(items) == 0,
    )
