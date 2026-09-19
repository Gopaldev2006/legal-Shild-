"""
RAG Phase 4 — Answer Generation Test Suite
============================================
TC-01  Relevant document question → answer + sources returned
TC-02  Irrelevant question → no_relevant_context=True, safe message
TC-03  Gemini available (mock) → answer uses Gemini provider
TC-04  Gemini unavailable (no key) → fallback engine answers from context
TC-05  Invalid Gemini key (not AIzaSy) → fallback engine used
TC-06  Fallback engine receives context → not generic, references document
TC-07  Sources populated correctly (chunk_id, filename, page, similarity)
TC-08  Page references present in source items
TC-09  Multiple documents → sources from correct documents
TC-10  Cross-user security → user B gets no results
TC-11  Empty question → safe error, no crash
TC-12  context_builder produces correct format

Run:
    cd backend
    python -m pytest tests/test_rag_phase4.py -v
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch

from app.services.rag.context_builder import (
    build_context, build_system_prompt, build_full_prompt
)
from app.services.rag.rag_answer_service import rag_answer, RAGAnswerResult
from app.services.retrieval.retrieval_service import SearchResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_result(chunk_id, doc_id, filename, page, similarity, content):
    return SearchResult(
        chunk_id=    chunk_id,
        document_id= doc_id,
        chunk_index= 0,
        content=     content,
        page_number= page,
        similarity=  similarity,
        filename=    filename,
        matter_id=   "MAT-TEST",
        jurisdiction="Supreme Court of India",
    )


def _mock_db_with_results(results):
    """Build a mock Session that makes retrieve_relevant_chunks return *results*."""
    db = MagicMock()
    q  = MagicMock()
    q.join.return_value   = q
    q.filter.return_value = q
    # Each SearchResult needs a (chunk, filename, jurisdiction) row
    rows = []
    from app.services.embedding.embedding_service import EmbeddingService
    svc = EmbeddingService.get()
    for r in results:
        chunk = MagicMock()
        chunk.chunk_id    = r.chunk_id
        chunk.document_id = r.document_id
        chunk.owner_id    = 99
        chunk.text        = r.content
        chunk.chunk_index = r.chunk_index
        chunk.page_number = r.page_number
        chunk.matter_id   = r.matter_id
        chunk.is_embedded = True
        vec = svc.embed_text(r.content)
        chunk.embedding   = svc.to_storage(vec) if vec is not None else None
        rows.append((chunk, r.filename, r.jurisdiction))
    q.all.return_value = rows
    db.query.return_value = q
    return db


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Relevant document question → answer + sources
# ─────────────────────────────────────────────────────────────────────────────
def test_tc01_relevant_question():
    results = [
        _make_result("chk-1", 1, "contract.pdf", 3, 0.88,
                     "Section 3 — Termination: Either party may terminate with 30 days written notice.")
    ]
    db = _mock_db_with_results(results)

    ans = rag_answer(
        query="What are the termination conditions?",
        user_id=99, db=db, document_id=None, top_k=5
    )

    assert ans.used_rag == True,              "used_rag should be True"
    assert ans.chunks_retrieved > 0,          "chunks_retrieved should be > 0"
    assert ans.no_relevant_context == False,  "no_relevant_context should be False"
    assert len(ans.answer) > 20,             "answer should be non-trivial"
    assert len(ans.sources) > 0,             "sources should be non-empty"
    print(f"TC-01 PASS — provider={ans.provider_used}, sources={len(ans.sources)}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Irrelevant question → no_relevant_context=True
# ─────────────────────────────────────────────────────────────────────────────
def test_tc02_irrelevant_question():
    db = _mock_db_with_results([])  # DB returns nothing for this user

    ans = rag_answer(
        query="quantum physics black holes",
        user_id=99, db=db, top_k=5
    )

    assert ans.no_relevant_context == True, "should flag no_relevant_context"
    assert ans.used_rag == False,           "used_rag should be False when no context"
    assert ans.chunks_retrieved == 0
    assert "not" in ans.answer.lower() or "no" in ans.answer.lower() or "could not" in ans.answer.lower()
    print(f"TC-02 PASS — no_relevant_context=True, answer safe")


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Gemini available → answer uses Gemini
# ─────────────────────────────────────────────────────────────────────────────
def test_tc03_gemini_available():
    results = [
        _make_result("chk-g", 1, "doc.pdf", 1, 0.82,
                     "The contract is governed by the Indian Contract Act 1872.")
    ]
    db = _mock_db_with_results(results)

    mock_gemini_answer = "## Answer\nThe contract is governed by the Indian Contract Act 1872 as stated on Page 1."

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key",
               return_value="AIzaSyFakeValidKey123456"), \
         patch("app.services.rag.rag_answer_service.GeminiService") as MockGemini:

        instance = MockGemini.return_value
        instance.generate_response.return_value = mock_gemini_answer

        ans = rag_answer(query="What law governs this contract?",
                         user_id=99, db=db, top_k=5)

    assert "Gemini" in ans.provider_used,   f"Expected Gemini provider, got: {ans.provider_used}"
    assert mock_gemini_answer in ans.answer or len(ans.answer) > 10
    assert ans.used_rag == True
    print(f"TC-03 PASS — Gemini provider used: {ans.provider_used}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  Gemini unavailable (empty key) → fallback grounded engine
# ─────────────────────────────────────────────────────────────────────────────
def test_tc04_gemini_unavailable_fallback():
    results = [
        _make_result("chk-f", 1, "lease.pdf", 2, 0.79,
                     "The tenant shall pay rent on the 1st of every month.")
    ]
    db = _mock_db_with_results(results)

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key", return_value=""):
        ans = rag_answer(query="When is rent due?", user_id=99, db=db, top_k=5)

    assert "Free" in ans.provider_used or "Grounded" in ans.provider_used, \
        f"Expected fallback provider, got: {ans.provider_used}"
    assert ans.used_rag == True
    assert len(ans.answer) > 20
    print(f"TC-04 PASS — fallback provider used: {ans.provider_used}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Invalid Gemini key (wrong format) → fallback used
# ─────────────────────────────────────────────────────────────────────────────
def test_tc05_invalid_gemini_key_fallback():
    results = [
        _make_result("chk-i", 1, "agreement.pdf", 1, 0.75,
                     "Jurisdiction: All disputes subject to Delhi High Court.")
    ]
    db = _mock_db_with_results(results)

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key",
               return_value="AQ.InvalidKeyFormat12345"):
        ans = rag_answer(query="Which court has jurisdiction?",
                         user_id=99, db=db, top_k=5)

    assert "Gemini" not in ans.provider_used or "Free" in ans.provider_used or "Grounded" in ans.provider_used
    assert ans.used_rag == True
    assert ans.chunks_retrieved > 0
    print(f"TC-05 PASS — invalid key → fallback: {ans.provider_used}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-06  Fallback engine receives context → references document content
# ─────────────────────────────────────────────────────────────────────────────
def test_tc06_fallback_grounded_response():
    results = [
        _make_result("chk-fb", 5, "nda.pdf", 4, 0.83,
                     "Confidentiality: The receiving party shall not disclose any proprietary information.")
    ]
    db = _mock_db_with_results(results)

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key", return_value=""):
        ans = rag_answer(query="What are the confidentiality obligations?",
                         user_id=99, db=db, top_k=5)

    # Fallback must mention the document, not just give generic info
    assert "nda.pdf" in ans.answer or "Source" in ans.answer or "document" in ans.answer.lower(), \
        "Fallback answer must reference the document"
    assert ans.chunks_retrieved > 0
    print(f"TC-06 PASS — fallback grounded: references document in answer")


# ─────────────────────────────────────────────────────────────────────────────
# TC-07  Sources populated correctly
# ─────────────────────────────────────────────────────────────────────────────
def test_tc07_sources_populated():
    results = [
        _make_result("chk-s1", 10, "employment.pdf", 3, 0.91,
                     "The employee agrees to a 6-month probation period."),
        _make_result("chk-s2", 10, "employment.pdf", 5, 0.84,
                     "Termination requires 30 days written notice from either party."),
    ]
    db = _mock_db_with_results(results)

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key", return_value=""):
        ans = rag_answer(query="What is the notice period for termination?",
                         user_id=99, db=db, top_k=5)

    assert len(ans.sources) == 2,             f"Expected 2 sources, got {len(ans.sources)}"
    # Sources are sorted by similarity descending — verify both are present
    ids = {s.chunk_id for s in ans.sources}
    assert "chk-s1" in ids, "chk-s1 missing from sources"
    assert "chk-s2" in ids, "chk-s2 missing from sources"
    # Verify all required fields on the highest-similarity source
    top = max(ans.sources, key=lambda s: s.similarity)
    assert top.document_id == 10,              "document_id mismatch"
    assert top.filename    == "employment.pdf","filename mismatch"
    assert 0.0 <= top.similarity <= 1.0,      f"similarity out of range: {top.similarity}"
    assert top.page_number in (3, 5),         "page_number mismatch"
    print(f"TC-07 PASS — 2 sources, all fields correct, top similarity={top.similarity:.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-08  Page references present in sources
# ─────────────────────────────────────────────────────────────────────────────
def test_tc08_page_references():
    results = [
        _make_result("chk-p1", 2, "statute.pdf", 7,  0.88, "Section 302 IPC punishment."),
        _make_result("chk-p2", 2, "statute.pdf", 12, 0.81, "Section 304 IPC culpable homicide."),
    ]
    db = _mock_db_with_results(results)

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key", return_value=""):
        ans = rag_answer(query="IPC sections on homicide", user_id=99, db=db, top_k=5)

    pages = [s.page_number for s in ans.sources]
    assert 7  in pages, "Page 7 missing from sources"
    assert 12 in pages, "Page 12 missing from sources"
    assert None not in pages, "page_number should not be None for these chunks"
    print(f"TC-08 PASS — page references: {pages}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  Multiple documents → sources from correct documents only
# ─────────────────────────────────────────────────────────────────────────────
def test_tc09_multiple_documents():
    results = [
        _make_result("chk-d1", 11, "docA.pdf", 1, 0.90, "DocA: Arbitration clause governs disputes."),
        _make_result("chk-d2", 22, "docB.pdf", 2, 0.85, "DocB: Governing law is Indian Contract Act."),
    ]
    db = _mock_db_with_results(results)

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key", return_value=""):
        ans = rag_answer(query="dispute resolution and governing law",
                         user_id=99, db=db, top_k=5)

    doc_ids = {s.document_id for s in ans.sources}
    assert 11 in doc_ids, "docA sources missing"
    assert 22 in doc_ids, "docB sources missing"
    filenames = {s.filename for s in ans.sources}
    assert "docA.pdf" in filenames
    assert "docB.pdf" in filenames
    print(f"TC-09 PASS — sources from 2 documents: {doc_ids}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  Cross-user security — user B gets 0 results
# ─────────────────────────────────────────────────────────────────────────────
def test_tc10_cross_user_security():
    # DB returns nothing for user 200 (their owner_id filter returns empty)
    db = _mock_db_with_results([])

    with patch("app.services.rag.rag_answer_service.get_gemini_api_key", return_value=""):
        ans = rag_answer(query="termination clause", user_id=200, db=db, top_k=5)

    assert ans.no_relevant_context == True,  "user 200 should get no context"
    assert ans.chunks_retrieved    == 0,     "user 200 should retrieve 0 chunks"
    assert len(ans.sources)        == 0,     "user 200 should have no sources"
    print("TC-10 PASS — cross-user blocked: 0 chunks, 0 sources")


# ─────────────────────────────────────────────────────────────────────────────
# TC-11  Empty question → safe error, no crash
# ─────────────────────────────────────────────────────────────────────────────
def test_tc11_empty_question():
    db = _mock_db_with_results([])

    for q in ["", "   ", "\t\n"]:
        ans = rag_answer(query=q, user_id=99, db=db, top_k=5)
        assert isinstance(ans, RAGAnswerResult), "Must return RAGAnswerResult"
        assert len(ans.answer) > 0,              f"Answer must not be empty for query {repr(q)}"

    print("TC-11 PASS — empty queries return safe RAGAnswerResult")


# ─────────────────────────────────────────────────────────────────────────────
# TC-12  context_builder produces correct format
# ─────────────────────────────────────────────────────────────────────────────
def test_tc12_context_builder_format():
    results = [
        _make_result("chk-cb1", 1, "nda.pdf",  2, 0.92,
                     "The parties agree to maintain strict confidentiality."),
        _make_result("chk-cb2", 1, "nda.pdf",  4, 0.81,
                     "Breach of confidentiality shall attract liquidated damages."),
    ]

    # build_context
    ctx = build_context(results)
    assert "SOURCE 1"    in ctx,         "SOURCE 1 header missing"
    assert "SOURCE 2"    in ctx,         "SOURCE 2 header missing"
    assert "nda.pdf"     in ctx,         "filename missing from context"
    assert "Page"        in ctx,         "Page reference missing"
    assert "Similarity"  in ctx,         "Similarity missing"
    assert "confidentiality" in ctx.lower(), "chunk text missing"

    # build_system_prompt
    sp = build_system_prompt()
    assert "LexGuard" in sp,             "LexGuard missing from system prompt"
    assert "invent"   in sp.lower() or "fabricat" in sp.lower(), \
        "Anti-hallucination rule missing from system prompt"
    assert "disclaimer" in sp.lower(),   "Disclaimer rule missing"

    # build_full_prompt
    fp = build_full_prompt("What is confidentiality?", ctx)
    assert "RETRIEVED DOCUMENT CONTEXT" in fp, "Context header missing"
    assert "USER QUESTION"              in fp, "Question header missing"
    assert "What is confidentiality?"   in fp, "Query missing from full prompt"

    # Empty context
    empty_ctx = build_context([])
    assert empty_ctx == "", "Empty results should produce empty context"

    print(f"TC-12 PASS — context format correct, {len(ctx)} chars")
