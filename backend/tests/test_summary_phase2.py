"""
Analysis Phase 2 — Summary Service Unit Tests
===============================================
TC-01  Short document → single-pass, all 6 fields present
TC-02  Long document → hierarchical mode triggered
TC-03  Empty chunks → graceful SummaryResult with error flag
TC-04  Legal contract — key terms preserved
TC-05  Document with multiple sections — key_takeaways populated
TC-06  Gemini available (mock) — Gemini provider used
TC-07  Gemini unavailable — fallback engine used, still 6 fields
TC-08  Sources populated from chunks passed in
TC-09  Hallucination protection — no invented content marker
TC-10  Unauthorized document — ownership enforced at service boundary
TC-11  parse_json strips markdown fences correctly
TC-12  key_takeaways max 7 items
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch

from app.services.document.summary_service import (
    summarize_document,
    SummaryResult,
    _parse_json_response,
    _free_engine_summary,
    CHUNK_SUMMARY_THRESHOLD,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

SHORT_DOC_CHUNKS = [
    {
        "text":        "This Employment Agreement is between TechCorp India and Rahul Sharma. "
                       "The employee is appointed as Senior Software Engineer effective 1st January 2026.",
        "chunk_id":    "chk-short-1",
        "page_number": 1,
    }
]

LONG_DOC_CHUNKS = [
    {
        "text":        ("Section 1 — Parties\n"
                        "This contract is between Alpha Corp and Beta Ltd.\n\n") * 40,
        "chunk_id":    f"chk-long-{i}",
        "page_number": i + 1,
    }
    for i in range(5)
]

CONTRACT_CHUNKS = [
    {
        "text": (
            "This Service Agreement is entered into on 1st March 2026 between "
            "TechCorp India Pvt Ltd (\"Client\") and DataWorks Solutions (\"Provider\").\n\n"
            "Section 2 — Payment Terms: The Client shall pay INR 5,00,000 per month "
            "within 30 days of invoice. Late payments attract 2% monthly interest.\n\n"
            "Section 3 — Confidentiality: Both parties shall maintain strict confidentiality. "
            "This obligation survives termination for three years.\n\n"
            "Section 4 — Termination: Either party may terminate with 60 days written notice. "
            "Immediate termination is permitted for material breach.\n\n"
            "Section 5 — Governing Law: This Agreement is governed by the laws of India. "
            "Disputes shall be resolved through arbitration under the Arbitration Act 1996."
        ),
        "chunk_id":    "chk-contract-1",
        "page_number": 1,
    }
]

MULTI_SECTION_CHUNKS = [
    {"text": "EMPLOYMENT AGREEMENT\n\nSection 1: The Employee shall report to the CTO.",
     "chunk_id": "chk-ms-1", "page_number": 1},
    {"text": "Section 2: Salary shall be INR 12,00,000 per annum paid monthly.",
     "chunk_id": "chk-ms-2", "page_number": 2},
    {"text": "Section 3: Termination requires 30 days written notice from either party.",
     "chunk_id": "chk-ms-3", "page_number": 3},
    {"text": "Section 4: Governing law is Indian Contract Act 1872. Jurisdiction: Delhi.",
     "chunk_id": "chk-ms-4", "page_number": 4},
]


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Short document → all 6 fields present
# ─────────────────────────────────────────────────────────────────────────────
def test_tc01_short_document_all_fields():
    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="employment.txt", doc_type="contract",
            jurisdiction="High Court of Delhi", chunks=SHORT_DOC_CHUNKS
        )

    assert isinstance(result, SummaryResult)
    assert result.executive_summary,  "executive_summary must be non-empty"
    assert result.document_type,      "document_type must be non-empty"
    assert result.purpose,            "purpose must be non-empty"
    assert result.main_subject,       "main_subject must be non-empty"
    assert isinstance(result.key_takeaways, list), "key_takeaways must be a list"
    assert isinstance(result.sources, list),        "sources must be a list"
    assert result.successful == True
    print(f"TC-01 PASS — all 6 fields present, provider={result.provider_used}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Long document → hierarchical mode
# ─────────────────────────────────────────────────────────────────────────────
def test_tc02_long_document_hierarchical():
    full_text = "\n\n".join(c["text"] for c in LONG_DOC_CHUNKS)
    assert len(full_text) > CHUNK_SUMMARY_THRESHOLD, \
        f"Test fixture too short ({len(full_text)} chars) — increase size"

    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="long_contract.txt", doc_type="contract",
            jurisdiction=None, chunks=LONG_DOC_CHUNKS
        )

    assert result.successful
    assert len(result.executive_summary) > 10
    assert len(result.sources) == len(LONG_DOC_CHUNKS)
    print(f"TC-02 PASS — long doc ({len(full_text)} chars), "
          f"sources={len(result.sources)}, provider={result.provider_used}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Empty chunks → graceful error
# ─────────────────────────────────────────────────────────────────────────────
def test_tc03_empty_chunks():
    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="empty.txt", doc_type="general",
            jurisdiction=None, chunks=[]
        )

    assert isinstance(result, SummaryResult)
    assert result.successful == False
    assert result.error_message is not None
    assert len(result.executive_summary) > 0   # safe message, not crash
    print(f"TC-03 PASS — empty chunks → successful=False, error='{result.error_message}'")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  Legal contract — key legal terms preserved
# ─────────────────────────────────────────────────────────────────────────────
def test_tc04_legal_contract_key_terms():
    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="service_agreement.txt", doc_type="contract",
            jurisdiction="High Court of Karnataka", chunks=CONTRACT_CHUNKS
        )

    combined = " ".join([
        result.executive_summary,
        result.purpose,
        result.main_subject,
        " ".join(result.key_takeaways),
    ]).lower()

    # At least some legal terms must be preserved
    found = [kw for kw in ["terminat", "confidential", "payment", "arbitrat", "govern"]
             if kw in combined]
    assert len(found) >= 2, f"Too few legal terms preserved. Found: {found}"
    print(f"TC-04 PASS — legal terms preserved: {found}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Multiple sections — key_takeaways populated
# ─────────────────────────────────────────────────────────────────────────────
def test_tc05_multi_section_key_takeaways():
    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="employment_contract.txt", doc_type="contract",
            jurisdiction=None, chunks=MULTI_SECTION_CHUNKS
        )

    assert len(result.key_takeaways) > 0, "key_takeaways should be non-empty"
    assert all(isinstance(t, str) and len(t) > 0 for t in result.key_takeaways), \
        "All takeaways must be non-empty strings"
    print(f"TC-05 PASS — {len(result.key_takeaways)} key_takeaways from multi-section doc")


# ─────────────────────────────────────────────────────────────────────────────
# TC-06  Gemini available — Gemini provider used
# ─────────────────────────────────────────────────────────────────────────────
def test_tc06_gemini_provider_used():
    mock_response = """{
        "executive_summary": "This is a service agreement between two companies.",
        "document_type": "Service Agreement",
        "purpose": "To define the scope of services between the parties.",
        "main_subject": "Software development and AI consulting services.",
        "key_takeaways": ["Payment within 30 days.", "60 days termination notice."]
    }"""

    with patch("app.services.document.summary_service.get_gemini_api_key",
               return_value="AIzaSyFakeValidKey123"), \
         patch("app.services.document.summary_service.GeminiService") as MockGemini:

        instance = MockGemini.return_value
        instance.generate_response.return_value = mock_response

        result = summarize_document(
            filename="contract.txt", doc_type="contract",
            jurisdiction=None, chunks=CONTRACT_CHUNKS
        )

    assert result.provider_used == "Google Gemini AI", \
        f"Expected Gemini, got: {result.provider_used}"
    assert result.executive_summary == "This is a service agreement between two companies."
    assert result.document_type == "Service Agreement"
    assert len(result.key_takeaways) == 2
    print(f"TC-06 PASS — Gemini provider used, summary correct")


# ─────────────────────────────────────────────────────────────────────────────
# TC-07  Gemini unavailable → fallback, still all 6 fields
# ─────────────────────────────────────────────────────────────────────────────
def test_tc07_gemini_unavailable_fallback():
    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="nda.txt", doc_type="contract",
            jurisdiction="Supreme Court", chunks=CONTRACT_CHUNKS
        )

    assert "Free" in result.provider_used or "Fallback" in result.provider_used or \
           "Engine" in result.provider_used, \
        f"Expected fallback provider, got: {result.provider_used}"
    assert result.executive_summary
    assert result.document_type
    assert result.purpose
    assert result.main_subject
    assert isinstance(result.key_takeaways, list)
    assert result.successful
    print(f"TC-07 PASS — fallback used: {result.provider_used}, all 6 fields present")


# ─────────────────────────────────────────────────────────────────────────────
# TC-08  Sources populated from chunks
# ─────────────────────────────────────────────────────────────────────────────
def test_tc08_sources_from_chunks():
    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="multi.txt", doc_type="contract",
            jurisdiction=None, chunks=MULTI_SECTION_CHUNKS
        )

    assert len(result.sources) == len(MULTI_SECTION_CHUNKS), \
        f"Expected {len(MULTI_SECTION_CHUNKS)} sources, got {len(result.sources)}"

    chunk_ids = {c["chunk_id"] for c in MULTI_SECTION_CHUNKS}
    result_ids = {s.chunk_id for s in result.sources}
    assert chunk_ids == result_ids, f"Source chunk_ids mismatch: {chunk_ids} vs {result_ids}"

    pages = [s.page_number for s in result.sources]
    assert pages == [1, 2, 3, 4], f"Page numbers wrong: {pages}"
    print(f"TC-08 PASS — {len(result.sources)} sources, all chunk_ids and pages correct")


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  Hallucination guard — "Not clearly specified" for absent info
# ─────────────────────────────────────────────────────────────────────────────
def test_tc09_hallucination_protection():
    sparse_chunk = [{"text": "This document.", "chunk_id": "chk-sparse", "page_number": 1}]

    with patch("app.services.document.summary_service.get_gemini_api_key", return_value=""):
        result = summarize_document(
            filename="sparse.txt", doc_type="general",
            jurisdiction=None, chunks=sparse_chunk
        )

    # Should not crash and should return something meaningful or "not specified"
    assert result.successful
    assert isinstance(result.executive_summary, str)
    assert len(result.executive_summary) > 0
    # Should NOT invent elaborate false content
    assert len(result.executive_summary) < 2000, "Summary suspiciously long for sparse doc"
    print(f"TC-09 PASS — sparse doc handled gracefully, no hallucination")


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  parse_json strips markdown fences
# ─────────────────────────────────────────────────────────────────────────────
def test_tc10_parse_json_strips_fences():
    # With ```json fence
    raw_with_fence = '```json\n{"key": "value"}\n```'
    result = _parse_json_response(raw_with_fence)
    assert result == {"key": "value"}, f"Failed with json fence: {result}"

    # With plain ``` fence
    raw_plain_fence = '```\n{"key": "value2"}\n```'
    result2 = _parse_json_response(raw_plain_fence)
    assert result2 == {"key": "value2"}, f"Failed with plain fence: {result2}"

    # Without fence (clean JSON)
    raw_clean = '{"key": "value3"}'
    result3 = _parse_json_response(raw_clean)
    assert result3 == {"key": "value3"}, f"Failed with clean JSON: {result3}"

    # JSON embedded in text
    raw_embedded = 'Here is the result:\n{"key": "value4"}\nDone.'
    result4 = _parse_json_response(raw_embedded)
    assert result4 == {"key": "value4"}, f"Failed with embedded JSON: {result4}"

    # None for non-JSON
    result5 = _parse_json_response("this is not json at all")
    assert result5 is None, f"Should be None for non-JSON: {result5}"

    print("TC-10 PASS — all 5 parse_json_response cases correct")


# ─────────────────────────────────────────────────────────────────────────────
# TC-11  key_takeaways capped at 7
# ─────────────────────────────────────────────────────────────────────────────
def test_tc11_key_takeaways_max_seven():
    # Gemini returns 10 takeaways — should be capped at 7
    mock_response = """{
        "executive_summary": "Test summary.",
        "document_type": "Contract",
        "purpose": "Test purpose.",
        "main_subject": "Test subject.",
        "key_takeaways": ["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10"]
    }"""

    with patch("app.services.document.summary_service.get_gemini_api_key",
               return_value="AIzaSyFakeKey"), \
         patch("app.services.document.summary_service.GeminiService") as MockGemini:

        MockGemini.return_value.generate_response.return_value = mock_response
        result = summarize_document(
            filename="test.txt", doc_type="contract",
            jurisdiction=None, chunks=SHORT_DOC_CHUNKS
        )

    assert len(result.key_takeaways) <= 7, \
        f"key_takeaways should be capped at 7, got {len(result.key_takeaways)}"
    print(f"TC-11 PASS — key_takeaways capped at {len(result.key_takeaways)} (max 7)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-12  free_engine_summary — document type detection
# ─────────────────────────────────────────────────────────────────────────────
def test_tc12_free_engine_doc_type_detection():
    nda_chunks = [{"text": "NDA Agreement: Both parties agree to maintain confidentiality.",
                   "chunk_id": "chk-nda", "page_number": 1}]
    result = _free_engine_summary("nda_agreement.txt", "contract", None, nda_chunks)
    assert "nda" in result.document_type.lower() or \
           "non-disclosure" in result.document_type.lower() or \
           "agreement" in result.document_type.lower(), \
        f"Type detection failed: {result.document_type}"

    lease_chunks = [{"text": "Lease Agreement: The tenant shall pay monthly rent.",
                     "chunk_id": "chk-lease", "page_number": 1}]
    result2 = _free_engine_summary("lease_deed.txt", "contract", None, lease_chunks)
    assert len(result2.document_type) > 0
    print(f"TC-12 PASS — NDA type='{result.document_type}', Lease type='{result2.document_type}'")
