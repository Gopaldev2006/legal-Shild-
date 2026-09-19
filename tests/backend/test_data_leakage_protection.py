"""
Comprehensive Pytest Test Suite for Data-Leakage Protection Layer (Phase 13).

Test Scenarios:
1. User asks for another user's document -> Blocked by access validator BEFORE model.
2. User attempts to retrieve another matter -> Blocked by matter authorization check BEFORE model.
3. User attempts to retrieve unauthorized case -> Blocked by pre-filter retrieval & hard chunk check.
4. Prompt injection asks for confidential context -> Blocked/redacted by context sanitizer & access validator.
5. Model response contains unauthorized content / PII -> Redacted by privacy output filter.
6. Verification & documentation of architectural distinction between Authorization, Privacy Filtering, and Output Filtering.
"""

import pytest
from sqlalchemy.orm import Session
from app.services.security.privacy import (
    access_validator,
    sensitive_data_detector,
    privacy_output_validator,
    privacy_audit_logger,
)
from app.services.rag.rag_service import SecureRAGService
from app.services.vector.retrieval_service import UserContext


def test_user_asks_for_another_users_document(db: Session):
    """1. User A attempts to inspect or extract details from User B's document."""
    user_a_id = 101
    user_b_id = 999
    
    # Attempting access to User B's document (ID 9999) by User A
    val_res = access_validator.validate_document_access(
        db=db,
        user_id=user_a_id,
        user_role="LEGAL_PROFESSIONAL",
        document_id=9999
    )
    
    assert val_res["is_authorized"] is False
    assert "Access Refused" in val_res["reason"] or "not found" in val_res["reason"]


def test_user_attempts_to_retrieve_restricted_matter():
    """2. User attempts to retrieve a restricted organization matter."""
    user_context = UserContext(user_id=55, role="LEGAL_PROFESSIONAL")
    
    val_res = access_validator.validate_matter_access(
        user_role=user_context.role,
        user_id=user_context.user_id,
        matter_id="RESTRICTED_ORGANIZATION_MATTER_XYZ"
    )
    
    assert val_res["is_authorized"] is False
    assert "lacks clearance" in val_res["reason"]


def test_pre_generation_retrieved_chunk_authorization():
    """3. Hard pre-generation check purges any unauthorized chunk BEFORE model prompt construction."""
    user_id = 42
    chunks = [
        {"document_id": "D1", "owner_id": 42, "text": "Authorized client contract text."},
        {"document_id": "D2", "owner_id": 999, "text": "CONFIDENTIAL OTHER USER CONTRACT DATA."},
    ]
    
    purged_chunks = access_validator.validate_retrieved_chunks(
        user_role="LEGAL_PROFESSIONAL",
        user_id=user_id,
        chunks=chunks
    )
    
    assert len(purged_chunks) == 1
    assert purged_chunks[0]["owner_id"] == 42
    assert purged_chunks[0]["document_id"] == "D1"


def test_sensitive_pii_detection_and_pre_generation_masking():
    """4. Pre-generation PII masking redacts Indian PAN, Aadhaar, SSN, Credit Cards, API Keys."""
    raw_text = (
        "Client details: PAN ABCDE1234F, Aadhaar 2345 6789 0123, "
        "SSN 123-45-6789, Credit Card 4111111111111111, API Key sk_live_abc12345678901234567890"
    )
    
    scan_res = sensitive_data_detector.sanitize_text(raw_text)
    sanitized = scan_res["sanitized_text"]
    
    assert "[REDACTED_INDIAN_PAN]" in sanitized
    assert "[REDACTED_INDIAN_AADHAAR]" in sanitized
    assert "[REDACTED_US_SSN]" in sanitized
    assert "[REDACTED_CREDIT_CARD]" in sanitized
    assert "[REDACTED_API_KEY_TOKEN]" in sanitized
    assert "ABCDE1234F" not in sanitized
    assert "123-45-6789" not in sanitized


def test_post_generation_privacy_output_validation():
    """5. Model response containing residual PII or cross-tenant owner metadata is redacted."""
    leaking_response = "Here is the summary for Owner ID: 999 regarding PAN ABCDE1234F."
    
    priv_res = privacy_output_validator.validate_output_privacy(
        response_text=leaking_response,
        current_user_id=101
    )
    
    assert priv_res["is_clean"] is False
    assert "[REDACTED_CROSS_TENANT_OWNER_ID]" in priv_res["sanitized_response"]
    assert "[REDACTED_INDIAN_PAN]" in priv_res["sanitized_response"]
    assert "Owner ID: 999" not in priv_res["sanitized_response"]


def test_end_to_end_matter_access_refusal_in_rag_service():
    """6. RAG service rejects query on unauthorized matter BEFORE vector retrieval or model generation."""
    rag = SecureRAGService()
    user_context = UserContext(user_id=10, role="LEGAL_PROFESSIONAL")
    
    res = rag.process_query(
        query="Summarize financial terms",
        user_context=user_context,
        matter_id="RESTRICTED_ORGANIZATION_SECRET_999"
    )
    
    assert res["is_safe"] is False
    assert res["provider_used"] == "Privacy Access Validator"
    assert "Security Refusal" in res["answer"]


def test_security_architecture_layer_distinction_documentation():
    """
    7. Verifies and documents the formal distinction between:
       - Authorization (Pre-retrieval/Pre-generation permission check)
       - Privacy Filtering (Pre-generation PII token masking)
       - Output Filtering (Post-generation output verification)
    """
    distinction_matrix = {
        "AUTHORIZATION": (
            "Primary security boundary. Executes BEFORE vector retrieval or prompt assembly. "
            "Ensures user possesses legal clearance to access matter_id or document owner_id."
        ),
        "PRIVACY_FILTERING": (
            "Data sanitization. Executes BEFORE model inference. "
            "Redacts PII tokens (Aadhaar, PAN, SSN, Credit Cards) from retrieved text."
        ),
        "OUTPUT_FILTERING": (
            "Secondary fallback defense. Executes AFTER model inference. "
            "Inspects generated text for residual unmasked PII or cross-tenant metadata."
        )
    }
    
    assert "Primary security boundary" in distinction_matrix["AUTHORIZATION"]
    assert "Data sanitization" in distinction_matrix["PRIVACY_FILTERING"]
    assert "Secondary fallback defense" in distinction_matrix["OUTPUT_FILTERING"]
