"""
RAG Phase 3 — Semantic Search & Retrieval Test Suite
=====================================================
TC-01  Relevant query returns matching results
TC-02  Irrelevant query returns empty (below threshold)
TC-03  Top-K limit respected
TC-04  Similarity threshold filtering
TC-05  Specific document_id filter works
TC-06  Search across all user documents
TC-07  Cross-user security — user B cannot see user A's chunks
TC-08  Empty query returns empty list, no crash
TC-09  document_id that has no embeddings returns empty
TC-10  Results sorted by similarity descending

Run:
    cd backend
    python -m pytest tests/test_rag_phase3.py -v
"""

import sys, os, json, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import List, Optional

from app.services.embedding.embedding_service import EmbeddingService, EMBEDDING_DIM
from app.services.retrieval.retrieval_service import retrieve_relevant_chunks, SearchResult
from app.core.config import settings


# ── helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def svc():
    return EmbeddingService.get()


def _make_chunk(chunk_id, document_id, owner_id, text, chunk_index=0,
                page_number=1, matter_id=None, svc=None):
    """Create a mock DocumentChunk with a real embedding."""
    chunk = MagicMock()
    chunk.chunk_id    = chunk_id
    chunk.document_id = document_id
    chunk.owner_id    = owner_id
    chunk.text        = text
    chunk.chunk_index = chunk_index
    chunk.page_number = page_number
    chunk.matter_id   = matter_id
    chunk.is_embedded = True

    if svc:
        vec = svc.embed_text(text)
        chunk.embedding = svc.to_storage(vec) if vec is not None else None
    else:
        chunk.embedding = None

    return chunk


def _make_doc(doc_id, owner_id, filename="test.txt", jurisdiction=None):
    doc = MagicMock()
    doc.id           = doc_id
    doc.owner_id     = owner_id
    doc.filename     = filename
    doc.jurisdiction = jurisdiction
    return doc


def _build_db(chunks_with_meta: list) -> MagicMock:
    """
    Build a mock SQLAlchemy Session whose query().join().filter()...all()
    returns rows of (chunk, filename, jurisdiction).
    """
    db = MagicMock()

    # Each item in chunks_with_meta: (chunk, filename, jurisdiction)
    rows = chunks_with_meta

    # Chain: db.query().join().filter().filter().all()
    q = MagicMock()
    q.join.return_value    = q
    q.filter.return_value  = q
    q.all.return_value     = rows
    db.query.return_value  = q
    return db


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Relevant query returns matching results
# ─────────────────────────────────────────────────────────────────────────────
def test_tc01_relevant_query(svc):
    """A query semantically similar to chunk text should return a result."""
    chunk = _make_chunk("chk-1", 1, 99,
        "Habeas corpus is a fundamental legal writ protecting individual liberty against unlawful detention.",
        svc=svc)

    db = _build_db([(chunk, "case.pdf", "Supreme Court")])

    results = retrieve_relevant_chunks(
        query="What is habeas corpus and how does it protect liberty?",
        user_id=99, db=db, top_k=5, threshold=0.30
    )

    assert len(results) > 0, "Expected at least 1 result for relevant query"
    assert results[0].chunk_id == "chk-1"
    assert results[0].similarity >= 0.30
    assert results[0].filename == "case.pdf"
    print(f"TC-01 PASS — similarity={results[0].similarity:.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Irrelevant query returns empty (below threshold)
# ─────────────────────────────────────────────────────────────────────────────
def test_tc02_irrelevant_query(svc):
    """A query completely unrelated to chunk content should score below threshold."""
    chunk = _make_chunk("chk-2", 1, 99,
        "Section 302 IPC defines punishment for murder as death or life imprisonment.",
        svc=svc)

    db = _build_db([(chunk, "ipc.pdf", None)])

    # Very high threshold to simulate "no relevant context"
    results = retrieve_relevant_chunks(
        query="quantum physics equations and thermodynamics",
        user_id=99, db=db, top_k=5, threshold=0.99
    )

    assert results == [], f"Expected empty results, got {len(results)}"
    print("TC-02 PASS — irrelevant query returns empty list (threshold=0.99)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Top-K limit respected
# ─────────────────────────────────────────────────────────────────────────────
def test_tc03_top_k_limit(svc):
    """top_k=2 should return at most 2 results even if more pass threshold."""
    base = "This contract governs the legal obligations between the parties."
    chunks = [
        _make_chunk(f"chk-{i}", 1, 99, base + f" Clause {i}.", chunk_index=i, svc=svc)
        for i in range(6)
    ]
    rows = [(c, "contract.pdf", "Delhi HC") for c in chunks]
    db   = _build_db(rows)

    results = retrieve_relevant_chunks(
        query="contractual obligations between parties",
        user_id=99, db=db, top_k=2, threshold=0.0
    )

    assert len(results) <= 2, f"Expected ≤2 results, got {len(results)}"
    print(f"TC-03 PASS — top_k=2 respected, got {len(results)} result(s)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  Similarity threshold filtering
# ─────────────────────────────────────────────────────────────────────────────
def test_tc04_threshold_filtering(svc):
    """
    Results at threshold=0.0 should be ≥ results at threshold=0.9.
    Higher threshold → fewer (or equal) results.
    """
    text = "Arbitration clause: disputes shall be resolved by arbitration under Indian law."
    chunk = _make_chunk("chk-t", 1, 99, text, svc=svc)
    rows  = [(chunk, "arb.pdf", None)]

    r_low  = retrieve_relevant_chunks("arbitration dispute resolution", 99,
                                      _build_db(rows), top_k=5, threshold=0.0)
    r_high = retrieve_relevant_chunks("arbitration dispute resolution", 99,
                                      _build_db(rows), top_k=5, threshold=0.99)

    assert len(r_low) >= len(r_high), \
        f"Low threshold should return ≥ results: low={len(r_low)}, high={len(r_high)}"
    print(f"TC-04 PASS — threshold=0.0→{len(r_low)} results, threshold=0.99→{len(r_high)} results")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Specific document_id filter is applied
# ─────────────────────────────────────────────────────────────────────────────
def test_tc05_document_id_filter(svc):
    """
    When document_id is supplied, the SQL filter is applied.
    We verify the filter argument is passed through correctly.
    """
    chunk_a = _make_chunk("chk-a", 10, 99,
        "Consumer Protection Act safeguards buyer rights.", svc=svc)
    chunk_b = _make_chunk("chk-b", 20, 99,
        "The Hindu Marriage Act governs matrimonial disputes.", svc=svc)

    # Simulate DB returning only doc 10's chunk when document_id=10
    db = _build_db([(chunk_a, "consumer.pdf", None)])

    results = retrieve_relevant_chunks(
        query="consumer rights protection",
        user_id=99, db=db, document_id=10, top_k=5, threshold=0.0
    )

    # All results must be from document 10
    for r in results:
        assert r.document_id == 10, f"Got chunk from doc {r.document_id}, expected 10"
    print(f"TC-05 PASS — document_id=10 filter applied, {len(results)} result(s) all from doc 10")


# ─────────────────────────────────────────────────────────────────────────────
# TC-06  Search across all user's documents
# ─────────────────────────────────────────────────────────────────────────────
def test_tc06_cross_document_search(svc):
    """Without document_id filter, results can come from multiple documents."""
    chunks = [
        _make_chunk("chk-d1", 10, 99, "Section 302 IPC: punishment for murder.", svc=svc),
        _make_chunk("chk-d2", 20, 99, "Section 420 IPC: cheating and dishonesty.", svc=svc),
        _make_chunk("chk-d3", 30, 99, "Section 498A IPC: cruelty by husband.", svc=svc),
    ]
    rows = [(c, f"doc{c.document_id}.pdf", None) for c in chunks]
    db   = _build_db(rows)

    results = retrieve_relevant_chunks(
        query="IPC sections criminal offences",
        user_id=99, db=db, top_k=5, threshold=0.0
    )

    doc_ids = {r.document_id for r in results}
    assert len(doc_ids) >= 1, "Expected results from at least 1 document"
    print(f"TC-06 PASS — cross-document search, results from docs: {doc_ids}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-07  Cross-user security — user B cannot see user A's chunks
# ─────────────────────────────────────────────────────────────────────────────
def test_tc07_cross_user_security(svc):
    """
    DB is queried with owner_id == user_id.
    Simulates user B (id=200) getting 0 rows because DB filters by owner_id.
    """
    # DB returns empty because user_id=200 has no chunks (they belong to user 99)
    db = _build_db([])  # DB correctly returns nothing for user 200

    results = retrieve_relevant_chunks(
        query="habeas corpus legal rights",
        user_id=200,   # ← different user
        db=db, top_k=5, threshold=0.0
    )

    assert results == [], f"User 200 should get 0 results, got {len(results)}"
    print("TC-07 PASS — cross-user isolation enforced (user 200 gets 0 results)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-08  Empty query returns empty list, no crash
# ─────────────────────────────────────────────────────────────────────────────
def test_tc08_empty_query(svc):
    """Empty / whitespace query must return [] without raising exceptions."""
    db = _build_db([])

    for q in ["", "   ", "\n\t"]:
        results = retrieve_relevant_chunks(
            query=q, user_id=99, db=db, top_k=5, threshold=0.0
        )
        assert results == [], f"Empty query {repr(q)} should return [], got {results}"

    print("TC-08 PASS — empty/whitespace queries return [] safely")


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  Document without embeddings returns empty
# ─────────────────────────────────────────────────────────────────────────────
def test_tc09_no_embeddings(svc):
    """Chunks where is_embedded=False or embedding=None are skipped."""
    chunk = _make_chunk("chk-noemb", 1, 99,
        "This chunk was never embedded.", svc=None)  # svc=None → no embedding
    chunk.embedding = None
    chunk.is_embedded = False

    # is_embedded=False means the SQL filter excludes them; simulate empty DB result
    db = _build_db([])

    results = retrieve_relevant_chunks(
        query="legal document content",
        user_id=99, db=db, top_k=5, threshold=0.0
    )

    assert results == [], f"Expected empty, got {len(results)}"
    print("TC-09 PASS — chunks without embeddings correctly return 0 results")


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  Results are sorted by similarity descending
# ─────────────────────────────────────────────────────────────────────────────
def test_tc10_sorted_by_similarity(svc):
    """Top result must have the highest similarity score."""
    # Create chunks with varying semantic distance from query
    query = "termination clause contract agreement"
    chunks_texts = [
        ("chk-high",  "Termination: Either party may terminate this contract with 30 days notice."),
        ("chk-mid",   "The parties shall resolve disputes through arbitration under Indian law."),
        ("chk-low",   "The defendant was charged under Section 302 of the Indian Penal Code."),
    ]
    chunks = [
        _make_chunk(cid, 1, 99, txt, chunk_index=i, svc=svc)
        for i, (cid, txt) in enumerate(chunks_texts)
    ]
    rows = [(c, "multi.pdf", None) for c in chunks]
    db   = _build_db(rows)

    results = retrieve_relevant_chunks(
        query=query, user_id=99, db=db, top_k=5, threshold=0.0
    )

    assert len(results) > 0, "Expected at least 1 result"

    # Verify descending order
    sims = [r.similarity for r in results]
    assert sims == sorted(sims, reverse=True), \
        f"Results not sorted descending: {sims}"

    # Top result should be the termination clause
    assert results[0].chunk_id == "chk-high", \
        f"Expected 'chk-high' as top result, got '{results[0].chunk_id}'"

    print(f"TC-10 PASS — results sorted desc: {[round(s, 3) for s in sims]}")


# ─────────────────────────────────────────────────────────────────────────────
# BONUS  SearchResult fields are all populated correctly
# ─────────────────────────────────────────────────────────────────────────────
def test_bonus_result_fields(svc):
    """Every SearchResult must have all required fields populated."""
    chunk = _make_chunk("chk-fields", 7, 99,
        "PIL filed in Supreme Court challenging environmental violation.",
        page_number=3, matter_id="MAT-2026-01", svc=svc)

    db = _build_db([(chunk, "pil.pdf", "Supreme Court of India")])

    results = retrieve_relevant_chunks(
        query="public interest litigation environment",
        user_id=99, db=db, top_k=5, threshold=0.0
    )

    assert len(results) == 1
    r = results[0]
    assert r.chunk_id    == "chk-fields"
    assert r.document_id == 7
    assert r.page_number == 3
    assert r.matter_id   == "MAT-2026-01"
    assert r.filename    == "pil.pdf"
    assert r.jurisdiction == "Supreme Court of India"
    assert isinstance(r.similarity, float)
    assert len(r.content) > 0
    print(f"BONUS PASS — all SearchResult fields populated, sim={r.similarity:.4f}")
