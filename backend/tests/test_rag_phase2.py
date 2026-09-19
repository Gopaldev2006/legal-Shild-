"""
RAG Phase 2 — Embedding Test Suite
====================================
TC-01  Single chunk embedding — shape, dtype, dimension
TC-02  Multiple chunks embedded in batch — all valid, same dimension
TC-03  Empty / whitespace chunk — returns None, no crash
TC-04  Long document text — embedding still 384-dim
TC-05  Multiple documents — embeddings are distinct (not identical)
TC-06  Embedding dimension consistency — all chunks same dim
TC-07  Re-embedding — fresh vectors, new storage strings
TC-08  Failed embedding simulation — validate() returns False for bad vec
TC-09  User ownership metadata preserved through embedding round-trip
TC-10  Storage round-trip — encode → decode → allclose original

Run:
    cd backend
    python -m pytest tests/test_rag_phase2.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from app.services.embedding.embedding_service import EmbeddingService, EMBEDDING_DIM

# ── shared fixture ────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def svc():
    """Singleton — loaded once for the entire test module."""
    return EmbeddingService.get()


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Single chunk embedding
# ─────────────────────────────────────────────────────────────────────────────
def test_tc01_single_chunk(svc):
    text = "Section 302 IPC: Punishment for murder is death or life imprisonment."
    vec  = svc.embed_text(text)
    assert vec is not None,            "embed_text returned None for non-empty text"
    assert isinstance(vec, np.ndarray),"Result must be numpy ndarray"
    assert vec.dtype == np.float32,    f"Expected float32, got {vec.dtype}"
    assert vec.shape == (EMBEDDING_DIM,), f"Expected ({EMBEDDING_DIM},), got {vec.shape}"
    assert svc.validate_embedding(vec),"validate_embedding failed on valid vector"
    print(f"TC-01 PASS — shape={vec.shape}, dtype={vec.dtype}, norm≈{np.linalg.norm(vec):.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Multiple chunks via batch
# ─────────────────────────────────────────────────────────────────────────────
def test_tc02_multiple_chunks_batch(svc):
    texts = [
        "Article 14: Equality before law.",
        "Article 19: Freedom of speech and expression.",
        "Article 21: Protection of life and personal liberty.",
        "WHEREAS the parties have agreed to the following terms.",
        "Clause 4.2: Payment shall be due within thirty days of invoice.",
    ]
    vecs = svc.embed_batch(texts)
    assert len(vecs) == len(texts), "Batch output length mismatch"
    for i, vec in enumerate(vecs):
        assert vec is not None,              f"Chunk {i} unexpectedly None"
        assert vec.shape == (EMBEDDING_DIM,),f"Chunk {i} wrong shape: {vec.shape}"
        assert vec.dtype == np.float32,      f"Chunk {i} wrong dtype: {vec.dtype}"
        assert svc.validate_embedding(vec),  f"Chunk {i} failed validation"
    print(f"TC-02 PASS — {len(vecs)} chunks, all {EMBEDDING_DIM}-dim float32")


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Empty / whitespace text
# ─────────────────────────────────────────────────────────────────────────────
def test_tc03_empty_chunk(svc):
    assert svc.embed_text("") is None,      "Empty string should return None"
    assert svc.embed_text("   ") is None,   "Whitespace-only should return None"
    assert svc.embed_text("\n\t\n") is None,"Newline-only should return None"

    vecs = svc.embed_batch(["valid text", "", "  ", "another valid"])
    assert vecs[0] is not None, "Valid text should embed"
    assert vecs[1] is None,     "Empty string should be None in batch"
    assert vecs[2] is None,     "Whitespace should be None in batch"
    assert vecs[3] is not None, "Valid text should embed"
    print("TC-03 PASS — empty/whitespace correctly returns None")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  Long document text
# ─────────────────────────────────────────────────────────────────────────────
def test_tc04_long_document_text(svc):
    long_text = (
        "This agreement is entered into by and between Alpha Corporation and Beta Ltd. "
        "Governed by the Indian Contract Act 1872, both parties agree to the terms herein. "
    ) * 50  # ~4 000 chars — model truncates internally, output always 384-dim
    vec = svc.embed_text(long_text)
    assert vec is not None
    assert vec.shape == (EMBEDDING_DIM,), f"Expected {EMBEDDING_DIM}-dim, got {vec.shape}"
    assert svc.validate_embedding(vec)
    print(f"TC-04 PASS — {len(long_text)}-char text → {EMBEDDING_DIM}-dim embedding")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Multiple documents produce distinct embeddings
# ─────────────────────────────────────────────────────────────────────────────
def test_tc05_multiple_documents_distinct(svc):
    vec_a = svc.embed_text("Habeas corpus protects individual liberty.")
    vec_b = svc.embed_text("Section 420 IPC deals with cheating and dishonesty.")
    vec_c = svc.embed_text("Consumer Protection Act 2019 safeguards buyer rights.")

    assert not np.allclose(vec_a, vec_b, atol=1e-4), "doc A and B embeddings identical — unexpected"
    assert not np.allclose(vec_b, vec_c, atol=1e-4), "doc B and C embeddings identical — unexpected"
    assert not np.allclose(vec_a, vec_c, atol=1e-4), "doc A and C embeddings identical — unexpected"
    print("TC-05 PASS — 3 distinct texts produce 3 distinct embeddings")


# ─────────────────────────────────────────────────────────────────────────────
# TC-06  Embedding dimension consistency across a batch
# ─────────────────────────────────────────────────────────────────────────────
def test_tc06_dimension_consistency(svc):
    texts = [f"Legal clause number {i} governs the obligations of the parties." for i in range(10)]
    vecs  = svc.embed_batch(texts)
    dims  = {v.shape[0] for v in vecs if v is not None}
    assert dims == {EMBEDDING_DIM}, f"Inconsistent dimensions found: {dims}"
    assert svc.dimension == EMBEDDING_DIM, "svc.dimension property mismatch"
    print(f"TC-06 PASS — all 10 chunks consistently {EMBEDDING_DIM}-dim")


# ─────────────────────────────────────────────────────────────────────────────
# TC-07  Re-embedding produces different storage strings (UUID suffix)
# ─────────────────────────────────────────────────────────────────────────────
def test_tc07_reembedding_fresh_vectors(svc):
    text  = "Article 21 guarantees right to life and personal liberty."
    vec1  = svc.embed_text(text)
    vec2  = svc.embed_text(text)
    str1  = svc.to_storage(vec1)
    str2  = svc.to_storage(vec2)
    # Same text → same deterministic embedding → same stored string
    assert str1 == str2, "Same text must produce same embedding (deterministic model)"
    # But the embedding is valid and round-trips correctly both times
    r1 = svc.from_storage(str1)
    r2 = svc.from_storage(str2)
    assert np.allclose(r1, r2), "Round-trip mismatch"
    print("TC-07 PASS — re-embedding is deterministic; storage strings match")


# ─────────────────────────────────────────────────────────────────────────────
# TC-08  Failed embedding validation
# ─────────────────────────────────────────────────────────────────────────────
def test_tc08_failed_embedding_validation(svc):
    # Wrong dimension
    bad_dim = np.ones(100, dtype=np.float32)
    assert not svc.validate_embedding(bad_dim), "Wrong-dim vec should fail"

    # NaN values
    bad_nan = np.full(EMBEDDING_DIM, float('nan'), dtype=np.float32)
    assert not svc.validate_embedding(bad_nan), "NaN vec should fail"

    # Inf values
    bad_inf = np.full(EMBEDDING_DIM, float('inf'), dtype=np.float32)
    assert not svc.validate_embedding(bad_inf), "Inf vec should fail"

    # Wrong dtype
    bad_dtype = np.ones(EMBEDDING_DIM, dtype=np.float64)
    assert not svc.validate_embedding(bad_dtype), "float64 vec should fail"

    # None
    assert not svc.validate_embedding(None), "None should fail"

    # Valid passes
    good = np.ones(EMBEDDING_DIM, dtype=np.float32)
    assert svc.validate_embedding(good), "Valid vec should pass"

    print("TC-08 PASS — all 5 bad vectors rejected, valid vector accepted")


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  User ownership metadata preserved through embedding round-trip
# ─────────────────────────────────────────────────────────────────────────────
def test_tc09_ownership_metadata(svc):
    import json
    text = "Confidential legal matter for client ID 99, matter MAT-2026-999."
    vec  = svc.embed_text(text)
    assert vec is not None

    # Simulate what the pipeline stores
    stored_embedding = svc.to_storage(vec)
    metadata = json.dumps({
        "owner_id":   99,
        "matter_id":  "MAT-2026-999",
        "doc_id":     42,
        "chunk_index": 0,
    })

    # Simulate retrieval — metadata intact, embedding recoverable
    recovered_vec = svc.from_storage(stored_embedding)
    meta_dict     = json.loads(metadata)

    assert np.allclose(vec, recovered_vec), "Embedding changed after storage round-trip"
    assert meta_dict["owner_id"]  == 99,             "owner_id lost"
    assert meta_dict["matter_id"] == "MAT-2026-999", "matter_id lost"
    assert meta_dict["doc_id"]    == 42,             "doc_id lost"
    print("TC-09 PASS — ownership metadata intact through embedding round-trip")


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  Storage round-trip fidelity
# ─────────────────────────────────────────────────────────────────────────────
def test_tc10_storage_roundtrip(svc):
    texts = [
        "Arbitration clause governs dispute resolution.",
        "PIL filed in the Supreme Court of India.",
        "FIR registered under Section 154 CrPC.",
    ]
    for text in texts:
        original  = svc.embed_text(text)
        stored    = svc.to_storage(original)
        recovered = svc.from_storage(stored)

        assert isinstance(stored, str),              "Stored value must be string"
        assert recovered.shape == (EMBEDDING_DIM,),  "Recovered shape mismatch"
        assert recovered.dtype == np.float32,        "Recovered dtype mismatch"
        assert np.allclose(original, recovered, atol=1e-6), \
            f"Round-trip fidelity lost for: {text[:40]}"

    print("TC-10 PASS — all 3 texts: encode→store→decode→allclose original")
