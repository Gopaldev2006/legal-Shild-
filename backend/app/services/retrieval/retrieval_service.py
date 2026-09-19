"""
RAG Phase 3 — Semantic Retrieval Service
=========================================
Owner-scoped cosine similarity search over DocumentChunk embeddings
stored in SQLite as base64-encoded float32 vectors.

Security guarantee
------------------
Every query is scoped to current_user.id FIRST — the WHERE clause on
owner_id is applied BEFORE any similarity computation. A user can never
receive chunks belonging to another user's documents.

Flow
----
query_text
  → preprocess (same as embed pipeline)
  → EmbeddingService.embed_text()        ← same model, same preprocessing
  → load owner-scoped embedded chunks from DB
  → cosine_similarity(query_vec, chunk_vec) for each chunk
  → filter by RAG_SIMILARITY_THRESHOLD
  → sort descending, take top_k
  → return SearchResult list
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import DocumentChunk, LegalDocument
from app.services.embedding.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


# ── result schema (dataclass — no ORM dependency) ────────────────────────────

@dataclass
class SearchResult:
    chunk_id:    str
    document_id: int
    chunk_index: int
    content:     str
    page_number: Optional[int]
    similarity:  float
    filename:    str
    matter_id:   Optional[str]
    jurisdiction: Optional[str]


# ── core function ─────────────────────────────────────────────────────────────

def retrieve_relevant_chunks(
    query:       str,
    user_id:     int,
    db:          Session,
    document_id: Optional[int] = None,
    top_k:       Optional[int] = None,
    threshold:   Optional[float] = None,
) -> List[SearchResult]:
    """
    Semantically retrieve the most relevant chunks for *query* from the
    documents owned by *user_id*.

    Parameters
    ----------
    query       : natural-language query string
    user_id     : MUST be current_user.id — enforced here, not by caller
    db          : SQLAlchemy session
    document_id : if given, restrict search to that document
    top_k       : how many results to return (default: settings.RAG_TOP_K)
    threshold   : minimum cosine similarity (default: settings.RAG_SIMILARITY_THRESHOLD)

    Returns
    -------
    List[SearchResult] ordered by similarity descending.
    Returns [] if no chunks pass the threshold (no_relevant_context).
    """
    _top_k     = top_k     if top_k     is not None else settings.RAG_TOP_K
    _threshold = threshold if threshold is not None else settings.RAG_SIMILARITY_THRESHOLD

    # ── 1. Validate & embed query ──────────────────────────────────────────
    clean_query = query.strip()
    if not clean_query:
        logger.warning("retrieve_relevant_chunks called with empty query")
        return []

    svc       = EmbeddingService.get()
    query_vec = svc.embed_text(clean_query)
    if query_vec is None:
        logger.warning("Query embedding returned None for: %r", clean_query)
        return []

    # ── 2. Load owner-scoped embedded chunks from DB ───────────────────────
    # Security: owner_id filter applied FIRST in SQL
    q = (
        db.query(DocumentChunk, LegalDocument.filename,
                 LegalDocument.jurisdiction)
        .join(LegalDocument, LegalDocument.id == DocumentChunk.document_id)
        .filter(
            DocumentChunk.owner_id   == user_id,   # SECURITY: owner scope
            DocumentChunk.is_embedded == True,      # only embedded chunks
        )
    )

    if document_id is not None:
        # Extra ownership check: document must also belong to this user
        q = q.filter(
            DocumentChunk.document_id == document_id,
            LegalDocument.owner_id    == user_id,   # belt-and-suspenders
        )

    rows = q.all()

    if not rows:
        logger.info(
            "No embedded chunks found for user_id=%d doc_id=%s",
            user_id, document_id,
        )
        return []

    # ── 3. Cosine similarity ───────────────────────────────────────────────
    # query_vec is already L2-normalised by SentenceTransformer
    # (normalize_embeddings=True) so cosine sim == dot product
    scored: List[tuple] = []

    for chunk, filename, jurisdiction in rows:
        if not chunk.embedding:
            continue
        try:
            chunk_vec = svc.from_storage(chunk.embedding)
        except Exception:
            logger.warning("Failed to decode embedding for chunk %s", chunk.chunk_id)
            continue

        # Both vectors are L2-normalised → dot product = cosine similarity
        sim = float(np.dot(query_vec, chunk_vec))

        if sim >= _threshold:
            scored.append((sim, chunk, filename, jurisdiction))

    # ── 4. Sort + take top_k ──────────────────────────────────────────────
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:_top_k]

    results = [
        SearchResult(
            chunk_id=    chunk.chunk_id,
            document_id= chunk.document_id,
            chunk_index= chunk.chunk_index,
            content=     chunk.text,
            page_number= chunk.page_number,
            similarity=  round(sim, 6),
            filename=    filename,
            matter_id=   chunk.matter_id,
            jurisdiction=jurisdiction,
        )
        for sim, chunk, filename, jurisdiction in top
    ]

    logger.info(
        "Retrieval: user=%d query=%r candidates=%d above_threshold=%d returned=%d",
        user_id, clean_query[:60], len(rows), len(scored), len(results),
    )
    return results
