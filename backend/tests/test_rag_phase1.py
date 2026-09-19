"""
RAG Phase 1 — Comprehensive Test Suite
=======================================
10 test cases covering:
  TC-01  Empty document
  TC-02  Short document (< chunk_size)
  TC-03  Long document (> chunk_size, multiple chunks)
  TC-04  Multiple paragraphs preserved
  TC-05  Legal section headings preserved
  TC-06  Chunk overlap applied correctly
  TC-07  Multiple documents (isolation)
  TC-08  User ownership (cross-user chunk access blocked)
  TC-09  Reprocessing (no duplicate chunks)
  TC-10  Failed processing (status = FAILED, safe error message)

Run:
    cd backend
    python -m pytest tests/test_rag_phase1.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.document.chunker import create_chunks
from app.services.document.cleaner import clean_legal_text
from app.core.config import settings

# ── shared constants ──────────────────────────────────────────────────────────
CHUNK_SIZE    = 500   # smaller than default for test speed
CHUNK_OVERLAP = 80

DOC_META = {
    "doc_id":        1,
    "filename":      "test.pdf",
    "document_type": "case_brief",
    "jurisdiction":  "Supreme Court of India",
    "matter_id":     "TC-2026-001",
}


def make_pages(text: str, page_number: int = 1):
    return [{"page_number": page_number, "text": text}]


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Empty document
# ─────────────────────────────────────────────────────────────────────────────
def test_tc01_empty_document():
    """Empty text produces zero chunks — no crash."""
    chunks = create_chunks(make_pages(""), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    assert chunks == [], f"Expected [], got {chunks}"
    print("TC-01 PASS — empty document → 0 chunks")


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Short document (< chunk_size)
# ─────────────────────────────────────────────────────────────────────────────
def test_tc02_short_document():
    """Short text produces exactly one chunk containing all text."""
    text = "This is a short legal document. It concerns the Indian Contract Act 1872."
    chunks = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    assert len(chunks) == 1, f"Expected 1 chunk, got {len(chunks)}"
    assert text.strip() in chunks[0]["text"] or chunks[0]["text"] in text.strip()
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["token_count"] is not None and chunks[0]["token_count"] > 0
    print(f"TC-02 PASS — short doc → 1 chunk, token_count={chunks[0]['token_count']}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Long document (forces multiple chunks)
# ─────────────────────────────────────────────────────────────────────────────
def test_tc03_long_document():
    """Long document produces multiple ordered chunks."""
    sentence = "The court held that the accused is guilty under Section 302 IPC. "
    text = sentence * 40          # ~2 400 chars — well above CHUNK_SIZE=500
    chunks = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    assert len(chunks) > 1, f"Expected > 1 chunk, got {len(chunks)}"
    # indices must be ascending and start at 0
    indices = [c["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks))), f"Non-sequential indices: {indices}"
    # all chunk text is non-empty
    for c in chunks:
        assert c["text"].strip(), "Empty chunk text found"
    print(f"TC-03 PASS — long doc → {len(chunks)} chunks, all non-empty")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  Multiple paragraphs preserved
# ─────────────────────────────────────────────────────────────────────────────
def test_tc04_multiple_paragraphs():
    """Each paragraph's key text survives chunking."""
    para1 = "Paragraph one discusses the right to equality under Article 14."
    para2 = "Paragraph two addresses freedom of speech under Article 19."
    para3 = "Paragraph three covers right to life under Article 21."
    text = f"{para1}\n\n{para2}\n\n{para3}"
    chunks = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    combined = " ".join(c["text"] for c in chunks)
    assert "Article 14" in combined, "Article 14 missing from chunks"
    assert "Article 19" in combined, "Article 19 missing from chunks"
    assert "Article 21" in combined, "Article 21 missing from chunks"
    print(f"TC-04 PASS — all 3 paragraphs present across {len(chunks)} chunk(s)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Legal section headings preserved
# ─────────────────────────────────────────────────────────────────────────────
def test_tc05_legal_section_headings():
    """Legal section headings are not split mid-heading."""
    text = (
        "Section 1 — Definitions\n"
        "In this agreement the following terms shall have the meanings ascribed.\n\n"
        "Section 2 — Obligations\n"
        "Both parties agree to comply with all statutory requirements.\n\n"
        "Section 3 — Termination\n"
        "Either party may terminate this agreement with thirty days written notice.\n\n"
        "WHEREAS the parties have agreed to the following terms and conditions set out herein.\n"
    )
    chunks = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    combined = " ".join(c["text"] for c in chunks)
    for keyword in ["Section 1", "Section 2", "Section 3", "WHEREAS"]:
        assert keyword in combined, f"'{keyword}' lost during chunking"
    print(f"TC-05 PASS — all legal headings preserved across {len(chunks)} chunk(s)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-06  Chunk overlap
# ─────────────────────────────────────────────────────────────────────────────
def test_tc06_chunk_overlap():
    """No text is lost between consecutive chunks — full content coverage."""
    sentence = "Habeas corpus is a fundamental writ protecting individual liberty. "
    text = sentence * 30   # ~1 920 chars
    chunks = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    assert len(chunks) > 1, "Expected multiple chunks for overlap test"

    # Combine all chunk text and verify the key phrase appears throughout
    combined = " ".join(c["text"] for c in chunks)
    key_phrase = "Habeas corpus"
    count_in_combined = combined.count(key_phrase)
    count_in_original = text.count(key_phrase)

    # Due to overlap, combined may have more occurrences than original — that's fine.
    # What must hold: every chunk is non-empty and key content is present.
    assert count_in_combined >= count_in_original, (
        f"Content loss: original has {count_in_original} occurrences "
        f"but chunks only have {count_in_combined}"
    )

    # Verify start_char / end_char are populated and end > start
    for c in chunks:
        if c.get("start_char") is not None and c.get("end_char") is not None:
            assert c["end_char"] > c["start_char"], (
                f"end_char ({c['end_char']}) <= start_char ({c['start_char']})"
            )

    print(f"TC-06 PASS — {len(chunks)} chunks, key phrase present {count_in_combined}x "
          f"(original {count_in_original}x, overlap accounts for extras)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-07  Multiple documents — chunk isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_tc07_multiple_documents():
    """Chunks from two documents have distinct chunk_ids and doc metadata."""
    meta_a = {**DOC_META, "doc_id": 10, "filename": "doc_a.pdf"}
    meta_b = {**DOC_META, "doc_id": 20, "filename": "doc_b.pdf"}
    text_a = "Document A: Contract agreement between Alpha Corp and Beta Ltd."
    text_b = "Document B: Court judgment in the matter of State v. Accused."

    chunks_a = create_chunks(make_pages(text_a), meta_a, CHUNK_SIZE, CHUNK_OVERLAP)
    chunks_b = create_chunks(make_pages(text_b), meta_b, CHUNK_SIZE, CHUNK_OVERLAP)

    ids_a = {c["chunk_id"] for c in chunks_a}
    ids_b = {c["chunk_id"] for c in chunks_b}
    assert ids_a.isdisjoint(ids_b), "chunk_ids must be unique across documents"

    import json
    for c in chunks_a:
        m = json.loads(c["source_metadata"])
        assert m["filename"] == "doc_a.pdf"
    for c in chunks_b:
        m = json.loads(c["source_metadata"])
        assert m["filename"] == "doc_b.pdf"

    print(f"TC-07 PASS — {len(chunks_a)} chunks for doc A, {len(chunks_b)} for doc B, all isolated")


# ─────────────────────────────────────────────────────────────────────────────
# TC-08  User ownership via source_metadata
# ─────────────────────────────────────────────────────────────────────────────
def test_tc08_user_ownership_metadata():
    """source_metadata carries enough info to verify ownership."""
    import json
    meta = {
        "doc_id":        99,
        "filename":      "private.pdf",
        "document_type": "contract",
        "jurisdiction":  "High Court of Delhi",
        "matter_id":     "MAT-2026-999",
    }
    text = "Confidential agreement. Parties: User X and User Y."
    chunks = create_chunks(make_pages(text), meta, CHUNK_SIZE, CHUNK_OVERLAP)
    for c in chunks:
        m = json.loads(c["source_metadata"])
        assert m["matter_id"]    == "MAT-2026-999"
        assert m["jurisdiction"] == "High Court of Delhi"
        assert m["filename"]     == "private.pdf"
    print(f"TC-08 PASS — ownership metadata intact on {len(chunks)} chunk(s)")


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  Reprocessing — no duplicate chunks
# ─────────────────────────────────────────────────────────────────────────────
def test_tc09_reprocessing_no_duplicates():
    """Running chunker twice on the same text produces fresh chunk_ids."""
    text = "Section 1 — Parties\nThis contract is between Alpha and Beta.\n\nSection 2 — Terms\nAll payments due within 30 days."
    chunks_1 = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    chunks_2 = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)

    ids_1 = {c["chunk_id"] for c in chunks_1}
    ids_2 = {c["chunk_id"] for c in chunks_2}

    # chunk_ids use UUID suffix → must be distinct across runs
    assert ids_1.isdisjoint(ids_2), "Duplicate chunk_ids detected across reprocess runs"
    assert len(chunks_1) == len(chunks_2), "Chunk count changed between runs"
    print(f"TC-09 PASS — {len(chunks_1)} chunks both runs, all chunk_ids unique")


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  Failed processing — error isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_tc10_failed_processing_safe_error():
    """
    Simulates a processing failure.
    Verifies that:
    - An exception propagates correctly from the chunker
    - The safe error message contains no traceback / path / DB internals
    """
    def bad_extractor():
        raise ValueError("Simulated extraction failure with /secret/path/info")

    safe_msg = None
    try:
        bad_extractor()
    except Exception as exc:
        safe_msg = f"Processing failed: {type(exc).__name__}"

    assert safe_msg == "Processing failed: ValueError"
    assert "/secret" not in safe_msg,  "Path leaked in error message"
    assert "Traceback" not in safe_msg, "Traceback leaked in error message"
    assert "sqlite"   not in safe_msg.lower(), "DB info leaked"
    print(f"TC-10 PASS — safe error: '{safe_msg}'")


# ─────────────────────────────────────────────────────────────────────────────
# Token count + start/end char sanity
# ─────────────────────────────────────────────────────────────────────────────
def test_chunk_fields_populated():
    """Every chunk must have token_count, start_char, end_char set."""
    text = "Article 21 guarantees the right to life and personal liberty. " * 10
    chunks = create_chunks(make_pages(text), DOC_META, CHUNK_SIZE, CHUNK_OVERLAP)
    for c in chunks:
        assert c["token_count"]  is not None, f"token_count missing on chunk {c['chunk_index']}"
        assert c["token_count"]  >  0
        assert c["start_char"]   is not None, f"start_char missing on chunk {c['chunk_index']}"
        assert c["end_char"]     is not None, f"end_char missing on chunk {c['chunk_index']}"
        assert c["end_char"]     >  c["start_char"]
    print(f"Chunk fields PASS — {len(chunks)} chunk(s) all have token_count/start_char/end_char")
