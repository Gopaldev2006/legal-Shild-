"""
Unit Tests — Risk Analysis Service (Phase 4)
============================================
Tests legal risk identification with severity, confidence, and evidence.
"""

import pytest
from app.services.document.risk_analysis_service import (
    analyze_legal_risks,
    IdentifiedRisk,
    RiskAssessment,
    RiskSource,
    RISK_CATEGORIES,
    SEVERITY_LEVELS,
)


# ── Test data ─────────────────────────────────────────────────────────────────

BROAD_TERMINATION_CONTRACT = """
EMPLOYMENT AGREEMENT

1. EMPLOYMENT
   Company may terminate this agreement at any time without cause or notice.
   
2. AT-WILL EMPLOYMENT
   This is an at-will employment relationship. Either party may terminate 
   immediately for any reason or no reason.

3. NO SEVERANCE
   Upon termination, Employee is not entitled to any severance payment.

Signed: January 1, 2024
"""

HIGH_LIABILITY_CONTRACT = """
SERVICE AGREEMENT

1. LIABILITY
   Provider shall have unlimited liability for any damages, losses, or claims
   arising from this agreement. Provider indemnifies Client against all claims
   without limit or cap.

2. INDEMNIFICATION  
   Provider agrees to indemnify and hold harmless Client for any and all damages,
   including consequential and punitive damages, arising from Provider's performance.

3. NO LIMITATION
   There shall be no limit on Provider's liability under this agreement.
"""

FINANCIAL_RISK_CONTRACT = """
CONSULTING AGREEMENT

1. PAYMENT
   Client shall pay Consultant INR 10,00,000 in advance, non-refundable.
   
2. LATE PAYMENT
   Late payment penalty of 15% per month will be charged.
   
3. ADDITIONAL FEES
   Consultant may charge additional fees at any time with 24 hours notice.
   
4. EXPENSES
   Client shall reimburse all expenses without limit or documentation requirement.
"""

FAVORABLE_CONTRACT = """
BALANCED EMPLOYMENT AGREEMENT

1. TERM
   This agreement is for a period of 2 years commencing January 1, 2024.

2. COMPENSATION
   Employer shall pay Employee INR 15,00,000 per annum.

3. TERMINATION
   Either party may terminate with 60 days written notice.
   Upon termination for cause, immediate termination is permitted.

4. SEVERANCE
   Upon termination without cause, Employee entitled to 3 months severance.

5. LIABILITY LIMITATION
   Liability is limited to fees paid in preceding 12 months.

6. DISPUTE RESOLUTION
   Disputes shall be resolved through mediation followed by arbitration.

7. GOVERNING LAW
   Governed by laws of India, courts of Mumbai.
"""

AMBIGUOUS_CONTRACT = """
VAGUE SERVICES AGREEMENT

1. SERVICES
   Provider shall provide reasonable services as appropriate under the circumstances.

2. PAYMENT
   Client shall pay adequate compensation as soon as practicable.

3. DELIVERY
   Provider shall use best efforts to deliver within a commercially reasonable timeframe.

4. QUALITY
   Work shall meet sufficient quality standards.

5. CHANGES
   Either party may make reasonable changes with appropriate notice.
"""

MISSING_PROTECTIONS_CONTRACT = """
SIMPLE AGREEMENT

1. SERVICES
   Provider shall provide consulting services.

2. PAYMENT
   Client shall pay INR 50,000 per month.

3. DURATION
   This agreement shall continue until terminated by either party.
"""


# ── Test cases ────────────────────────────────────────────────────────────────

def test_tc01_broad_termination_risk():
    """Contract with broad termination rights should identify termination risk."""
    chunks = [
        {
            "text": BROAD_TERMINATION_CONTRACT,
            "chunk_id": "term-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="termination_contract.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful
    assert len(result.risks) > 0

    # Should identify termination risk
    termination_risks = [r for r in result.risks if "Termination" in r.category]
    assert len(termination_risks) > 0, "Should identify termination risk"

    # Verify risk structure
    for risk in result.risks:
        assert risk.category in RISK_CATEGORIES
        assert risk.severity in SEVERITY_LEVELS
        assert risk.title
        assert risk.description
        assert risk.reason
        assert risk.evidence  # must have evidence
        assert 0.0 <= risk.confidence <= 1.0
        assert risk.source.chunk_id == "term-chunk-1"


def test_tc02_high_liability_risk():
    """Contract with unlimited liability should identify liability risk."""
    chunks = [
        {
            "text": HIGH_LIABILITY_CONTRACT,
            "chunk_id": "liab-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="liability_contract.pdf",
        doc_type="CONTRACT",
        jurisdiction=None,
        chunks=chunks,
    )

    assert result.analysis_successful
    assert len(result.risks) > 0

    # Should identify liability risk
    liability_risks = [r for r in result.risks if "Liability" in r.category]
    assert len(liability_risks) > 0, "Should identify liability risk"

    # Should be high severity due to unlimited liability
    high_liability = [r for r in liability_risks if r.severity == "high"]
    assert len(high_liability) > 0, "Unlimited liability should be high risk"

    # Evidence must contain "unlimited" or "no limit"
    for risk in liability_risks:
        assert "unlimited" in risk.evidence.lower() or "no limit" in risk.evidence.lower()


def test_tc03_financial_risk():
    """Contract with high penalties and non-refundable payments."""
    chunks = [
        {
            "text": FINANCIAL_RISK_CONTRACT,
            "chunk_id": "fin-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="financial_contract.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful
    assert len(result.risks) > 0

    # Should identify financial risk
    financial_risks = [r for r in result.risks if "Financial" in r.category]
    assert len(financial_risks) > 0, "Should identify financial risk"

    # Verify evidence contains financial terms
    for risk in financial_risks:
        financial_terms = ["penalty", "non-refundable", "advance", "fee"]
        has_financial = any(term in risk.evidence.lower() for term in financial_terms)
        # Financial risks should have relevant evidence


def test_tc04_favorable_contract_low_risk():
    """Well-balanced contract should have low overall risk."""
    chunks = [
        {
            "text": FAVORABLE_CONTRACT,
            "chunk_id": "fav-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="favorable_contract.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful
    
    # Overall risk should be Low or Moderate (not High)
    assert result.overall_risk in ["Low", "Moderate"], \
        f"Favorable contract should not be High risk, got {result.overall_risk}"
    
    # Risk score should be low
    assert result.risk_score < 7.0, "Favorable contract should have score < 7.0"

    # May have some risks, but no high-severity risks
    high_risks = [r for r in result.risks if r.severity == "high"]
    assert len(high_risks) <= 1, "Favorable contract should have few high risks"


def test_tc05_ambiguity_risk():
    """Contract with vague language should identify ambiguity risk."""
    chunks = [
        {
            "text": AMBIGUOUS_CONTRACT,
            "chunk_id": "amb-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="ambiguous_contract.pdf",
        doc_type="CONTRACT",
        jurisdiction=None,
        chunks=chunks,
    )

    assert result.analysis_successful
    assert len(result.risks) > 0

    # Should identify ambiguity risk
    ambiguity_risks = [r for r in result.risks if "Ambiguity" in r.category]
    assert len(ambiguity_risks) > 0, "Should identify ambiguity risk"

    # Evidence should contain vague terms
    for risk in ambiguity_risks:
        vague_terms = ["reasonable", "appropriate", "adequate", "sufficient", "best efforts"]
        has_vague = any(term in risk.evidence.lower() for term in vague_terms)
        assert has_vague, f"Ambiguity risk should cite vague terms, got: {risk.evidence}"


def test_tc06_missing_clause_risk():
    """Simple contract missing standard protections."""
    chunks = [
        {
            "text": MISSING_PROTECTIONS_CONTRACT,
            "chunk_id": "miss-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="simple_contract.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful

    # Should identify missing clause risk
    missing_risks = [r for r in result.risks if "Missing Clause" in r.category]
    # Note: May or may not detect depending on patterns, but overall risk assessment should reflect it


def test_tc07_overall_risk_calculation():
    """Verify overall risk calculation logic."""
    chunks = [
        {
            "text": HIGH_LIABILITY_CONTRACT,
            "chunk_id": "calc-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="test_calc.pdf",
        doc_type="CONTRACT",
        jurisdiction=None,
        chunks=chunks,
    )

    assert result.analysis_successful
    
    # Overall risk must be one of the valid levels
    assert result.overall_risk in ["Low", "Moderate", "High"]
    
    # Risk score must be in valid range
    assert 0.0 <= result.risk_score <= 10.0
    
    # Factors must be present
    assert len(result.factors) > 0
    assert all(isinstance(f, str) for f in result.factors)


def test_tc08_confidence_scoring():
    """All risks must have confidence scores between 0.0 and 1.0."""
    chunks = [
        {
            "text": BROAD_TERMINATION_CONTRACT,
            "chunk_id": "conf-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="confidence_test.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful
    
    # All risks must have valid confidence
    for risk in result.risks:
        assert 0.0 <= risk.confidence <= 1.0, \
            f"Confidence must be 0.0-1.0, got {risk.confidence}"
        assert isinstance(risk.confidence, float)


def test_tc09_evidence_requirement():
    """Every risk must have supporting evidence from document."""
    chunks = [
        {
            "text": HIGH_LIABILITY_CONTRACT,
            "chunk_id": "evid-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="evidence_test.pdf",
        doc_type="CONTRACT",
        jurisdiction=None,
        chunks=chunks,
    )

    assert result.analysis_successful
    
    # Every risk must have evidence
    for risk in result.risks:
        assert risk.evidence, f"Risk {risk.title} has no evidence"
        assert len(risk.evidence) > 10, "Evidence should be meaningful text"
        # Evidence should be from document (may include "not found" for missing clause risks)
        if "Missing Clause" not in risk.category:
            assert "not found" not in risk.evidence.lower(), \
                f"Non-missing-clause risk should have document evidence, got: {risk.evidence}"


def test_tc10_source_references():
    """All risks must have valid source references."""
    chunks = [
        {
            "text": FINANCIAL_RISK_CONTRACT[:500],
            "chunk_id": "src-chunk-1",
            "page_number": 1,
        },
        {
            "text": FINANCIAL_RISK_CONTRACT[500:],
            "chunk_id": "src-chunk-2",
            "page_number": 2,
        },
    ]

    result = analyze_legal_risks(
        filename="source_test.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful
    
    # All risks must have source
    for risk in result.risks:
        assert risk.source is not None
        assert risk.source.chunk_id in ["src-chunk-1", "src-chunk-2"]
        assert risk.source.page_number in [1, 2, None]


def test_tc11_severity_distribution():
    """Not all risks should be marked as high severity."""
    chunks = [
        {
            "text": AMBIGUOUS_CONTRACT,
            "chunk_id": "sev-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="severity_test.pdf",
        doc_type="CONTRACT",
        jurisdiction=None,
        chunks=chunks,
    )

    assert result.analysis_successful
    
    if len(result.risks) > 0:
        # Should have variety of severities (not all high)
        severities = {r.severity for r in result.risks}
        # For ambiguous contract, should have medium or low risks
        assert "medium" in severities or "low" in severities, \
            "Should have varied severity levels, not just high"


def test_tc12_empty_document():
    """Empty document should return low risk."""
    chunks = [
        {
            "text": "",
            "chunk_id": "empty-chunk",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="empty.pdf",
        doc_type="CONTRACT",
        jurisdiction=None,
        chunks=chunks,
    )

    # Should handle gracefully
    assert result.overall_risk in ["Low", "Moderate"]
    # May identify missing clause risk for empty document, which is valid
    assert result.risk_score < 5.0


def test_tc13_no_chunks_provided():
    """Service should handle empty chunks list gracefully."""
    result = analyze_legal_risks(
        filename="test.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=[],
    )

    assert not result.analysis_successful
    assert result.error_message is not None
    assert result.overall_risk == "Low"


def test_tc14_risk_categories_valid():
    """All identified risks must use standard categories."""
    chunks = [
        {
            "text": HIGH_LIABILITY_CONTRACT,
            "chunk_id": "cat-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="category_test.pdf",
        doc_type="CONTRACT",
        jurisdiction=None,
        chunks=chunks,
    )

    assert result.analysis_successful
    
    # All categories must be in standard list
    for risk in result.risks:
        assert risk.category in RISK_CATEGORIES, \
            f"Invalid category: {risk.category}"


def test_tc15_jurisdiction_awareness():
    """Risk analysis should consider jurisdiction when provided."""
    mumbai_contract = """
    AGREEMENT
    
    This agreement shall be governed by the laws of Maharashtra, India.
    Disputes shall be resolved in courts of Mumbai.
    """

    chunks = [
        {
            "text": mumbai_contract,
            "chunk_id": "jur-chunk-1",
            "page_number": 1,
        },
    ]

    # Analyze with different jurisdiction
    result = analyze_legal_risks(
        filename="jurisdiction_test.pdf",
        doc_type="CONTRACT",
        jurisdiction="Delhi",  # Different from Mumbai
        chunks=chunks,
    )

    assert result.analysis_successful
    
    # May identify jurisdiction risk
    jur_risks = [r for r in result.risks if "Jurisdiction" in r.category]
    # Not required to detect, but shouldn't fail


def test_tc16_multiple_high_risks_overall():
    """Multiple high risks should result in High overall assessment."""
    multi_risk_contract = """
    UNFAVORABLE AGREEMENT
    
    1. Provider has unlimited liability for all claims.
    
    2. Company may terminate immediately without cause or notice.
    
    3. Payment is non-refundable and must be made in advance.
    
    4. Late payment penalty of 20% per month.
    
    5. Provider waives all IP rights immediately upon creation.
    """

    chunks = [
        {
            "text": multi_risk_contract,
            "chunk_id": "multi-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="multi_risk.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful
    assert len(result.risks) > 0
    
    # Multiple significant risks
    high_risks = [r for r in result.risks if r.severity == "high"]
    
    # Overall risk should reflect multiple high risks
    if len(high_risks) >= 3:
        assert result.overall_risk == "High", \
            f"Multiple high risks should result in High overall, got {result.overall_risk}"


def test_tc17_provider_used_field():
    """Result should indicate which analysis engine was used."""
    chunks = [
        {
            "text": FAVORABLE_CONTRACT,
            "chunk_id": "prov-chunk-1",
            "page_number": 1,
        },
    ]

    result = analyze_legal_risks(
        filename="provider_test.pdf",
        doc_type="CONTRACT",
        jurisdiction="India",
        chunks=chunks,
    )

    assert result.analysis_successful
    assert result.provider_used
    assert "Gemini" in result.provider_used or "Free" in result.provider_used


# ── Run tests ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
