"""
Comprehensive Pytest Test Suite for Decoupled Citation Verification Engine.

Tests:
1. Valid citation verification matching DB & authorized retrieved context
2. Invalid citation verification (non-existent doc/chunk in system DB)
3. Unauthorized citation verification (document/chunk belonging to another user)
4. Missing source handling (empty context enforces mandatory evidence refusal)
5. Fabricated citation detection (catching hallucinated doc/chunk IDs not in retrieved context)
6. Decoupled verification execution (verification works independently of LLM generation)
"""

import pytest
from sqlalchemy.orm import Session
from app.models.user import User, UserRole, VerificationStatus
from app.models.document import LegalDocument, DocumentChunk, DocumentType, ProcessingStatus
from app.core.security import get_password_hash
from app.services.rag.citation_validator import citation_validator, CitationValidator
from app.services.vector.retrieval_service import UserContext


def test_valid_citation(db: Session):
    """1. Valid citation matching DB & authorized retrieved context."""
    user = User(
        name="Adv. Citation Tester",
        email="citation_user@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    doc = LegalDocument(
        owner_id=user.id,
        filename="valid_contract.pdf",
        stored_filename="valid_contract.pdf",
        stored_path="/tmp/valid.pdf",
        file_type="pdf",
        file_size=1024,
        file_hash="hash_valid",
        document_type=DocumentType.CONTRACT,
        processing_status=ProcessingStatus.COMPLETED
    )
    db.add(doc)
    db.commit()

    chunk = DocumentChunk(
        chunk_id=f"chk_valid_{doc.id}_1",
        document_id=doc.id,
        owner_id=user.id,
        text="Section 10: Both parties agree to arbitration in New Delhi.",
        chunk_index=0,
        page_number=2
    )
    db.add(chunk)
    db.commit()

    context_chunks = [{
        "document_id": doc.id,
        "filename": doc.filename,
        "chunk_id": chunk.chunk_id,
        "page_number": 2,
        "owner_id": user.id,
        "similarity_score": 0.95,
        "text": chunk.text
    }]

    user_context = UserContext(user_id=user.id, role="LEGAL_PROFESSIONAL")

    # Extract citations
    citations = citation_validator.extract_citations(context_chunks, db=db)
    assert len(citations) == 1
    cit = citations[0]
    
    assert cit["document_id"] == doc.id
    assert cit["document_name"] == "valid_contract.pdf"
    assert cit["page"] == 2
    assert cit["chunk_id"] == chunk.chunk_id
    assert cit["relevance"] == 0.95

    # Single citation verification
    check = citation_validator.verify_single_citation(
        citation=cit,
        authorized_context_chunks=context_chunks,
        user_context=user_context,
        db=db
    )
    assert check["is_valid"] is True
    assert check["is_authorized"] is True
    assert check["is_fabricated"] is False


def test_invalid_citation(db: Session):
    """2. Invalid citation referencing non-existent doc ID / chunk ID."""
    invalid_citation = {
        "document_id": 99999,
        "document_name": "ghost_document.pdf",
        "page": 1,
        "chunk_id": "chk_ghost_99999_1",
        "relevance": 0.5,
        "owner_id": 1
    }
    
    context_chunks = []
    user_context = UserContext(user_id=1, role="LEGAL_PROFESSIONAL")

    check = citation_validator.verify_single_citation(
        citation=invalid_citation,
        authorized_context_chunks=context_chunks,
        user_context=user_context,
        db=db
    )
    
    assert check["is_valid"] is False
    assert check["is_fabricated"] is True
    assert any("does not exist" in r for r in check["failure_reasons"])


def test_unauthorized_citation(db: Session):
    """3. Citation referencing another user's document/chunk."""
    user_a_id = 100
    user_b_id = 200

    unauthorized_citation = {
        "document_id": 50,
        "document_name": "other_user_private_brief.pdf",
        "page": 5,
        "chunk_id": "chk_50_1",
        "relevance": 0.88,
        "owner_id": user_b_id  # Belongs to User B
    }

    context_chunks = [{
        "document_id": 50,
        "chunk_id": "chk_50_1",
        "owner_id": user_b_id,
        "text": "Private text of User B"
    }]

    user_a_context = UserContext(user_id=user_a_id, role="LEGAL_PROFESSIONAL")

    check = citation_validator.verify_single_citation(
        citation=unauthorized_citation,
        authorized_context_chunks=context_chunks,
        user_context=user_a_context,
        db=db
    )

    assert check["is_authorized"] is False
    assert check["is_valid"] is False
    assert any("belongs to another user" in r for r in check["failure_reasons"])


def test_missing_source_evidence_refusal():
    """4. Query with empty context enforces mandatory evidence refusal message."""
    response = citation_validator.validate_response(
        response_text="Some hallucinated answer",
        context_chunks=[]
    )

    assert response["is_grounded"] is False
    assert response["final_text"] == CitationValidator.NO_EVIDENCE_REFUSAL
    assert len(response["citations"]) == 0


def test_fabricated_citation_detection():
    """5. Model response citing fake/hallucinated doc IDs detected and flagged as fabricated."""
    context_chunks = [{
        "document_id": 10,
        "chunk_id": "chk_10_1",
        "page_number": 1,
        "owner_id": 1,
        "text": "Legitimate section text."
    }]
    
    # Model generates text citing fake Doc #999 which was NOT in context
    fake_model_response = (
        "According to precedent [Doc #999, Page 4], the contract is void ab initio."
    )

    val_res = citation_validator.validate_response(
        response_text=fake_model_response,
        context_chunks=context_chunks,
        user_context=UserContext(user_id=1, role="LEGAL_PROFESSIONAL")
    )

    assert val_res["contains_fabricated_citations"] is True
    assert val_res["is_grounded"] is False
    assert "Fabricated citations detected" in val_res["validation_notes"]


def test_decoupled_verification_execution():
    """6. Verifies citation verification functions independently of model generation."""
    chunks = [
        {"document_id": 1, "filename": "doc1.txt", "chunk_id": "c1", "page_number": 1, "owner_id": 5, "similarity_score": 0.9}
    ]
    citations = citation_validator.extract_citations(chunks)
    
    assert len(citations) == 1
    assert citations[0]["document_id"] == 1
    assert citations[0]["document_name"] == "doc1.txt"
    assert citations[0]["page"] == 1
    assert citations[0]["chunk_id"] == "c1"
    assert citations[0]["relevance"] == 0.9
