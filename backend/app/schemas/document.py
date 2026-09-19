from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.document import ProcessingStatus, DocumentType


class DocumentResponse(BaseModel):
    id:                int
    owner_id:          int
    filename:          str
    file_type:         str
    file_size:         int
    file_hash:         str
    document_type:     DocumentType
    jurisdiction:      Optional[str] = None
    matter_id:         Optional[str] = None
    processing_status: ProcessingStatus
    error_message:     Optional[str] = None
    chunk_count:       int = 0
    embedded_count:    int = 0   # Phase 2: how many chunks have embeddings
    created_at:        datetime
    updated_at:        datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkResponse(BaseModel):
    id:              int
    chunk_id:        str
    document_id:     int
    owner_id:        int
    matter_id:       Optional[str] = None
    text:            str
    page_number:     Optional[int] = None
    chunk_index:     int
    start_char:      Optional[int] = None
    end_char:        Optional[int] = None
    token_count:     Optional[int] = None
    source_metadata: Optional[str] = None
    # Phase 2 — embedding fields (embedding bytes not returned to client)
    embedding_dim:   Optional[int]  = None
    is_embedded:     bool           = False
    created_at:      datetime

    model_config = ConfigDict(from_attributes=True)


class ReprocessResponse(BaseModel):
    document_id:       int
    filename:          str
    processing_status: ProcessingStatus
    chunk_count:       int
    message:           str


# ── Phase 4+: Document Analysis schema ───────────────────────────────────────

class SummarySourceSchema(BaseModel):
    page_number: Optional[int] = None
    chunk_id:    str


class StructuredSummarySchema(BaseModel):
    executive_summary: str
    document_type:     str
    purpose:           str
    main_subject:      str
    key_takeaways:     List[str]
    sources:           List[SummarySourceSchema] = []
    provider_used:     str


# ── Phase 3: Clause Analysis schemas ─────────────────────────────────────────

class ClauseSourceSchema(BaseModel):
    page_number: Optional[int] = None
    chunk_id:    str


class ImportantClauseSchema(BaseModel):
    clause_type: str  # "Termination", "Payment", "Confidentiality", etc.
    title:       str  # human-readable title
    description: str  # explanation of what the clause says
    importance:  str  # "high", "medium", "low"
    source:      ClauseSourceSchema


class ObligationSchema(BaseModel):
    """Obligation schema - supports both Phase 3 and Phase 6"""
    party:      str              # "Employee", "Client", "Provider", etc.
    obligation: str              # what the party must do/not do
    deadline:   str              # "Within 30 days", "Not specified", etc.
    source:     ClauseSourceSchema
    # Phase 6 enhancements:
    condition:  Optional[str] = None    # Phase 6: conditional requirement
    evidence:   Optional[str] = None    # Phase 6: evidence quote


# ── Phase 4: Risk Analysis schemas ───────────────────────────────────────────

class RiskSourceSchema(BaseModel):
    page_number: Optional[int] = None
    chunk_id:    str


class IdentifiedRiskSchema(BaseModel):
    category:    str    # "Financial Risk", "Termination Risk", etc.
    severity:    str    # "high", "medium", "low"
    title:       str    # brief description
    description: str    # detailed explanation
    reason:      str    # why this is risky
    evidence:    str    # supporting document text
    confidence:  float  # 0.0 - 1.0
    source:      RiskSourceSchema


class RiskAssessmentSchema(BaseModel):
    overall_risk:    str                          # "Low", "Moderate", "High"
    risk_score:      float                        # 0.0 - 10.0
    factors:         List[str]                    # contributing factors
    risks:           List[IdentifiedRiskSchema]   # individual identified risks
    provider_used:   str                          # AI engine used


# ── Phase 5: Missing and Ambiguous Clause schemas ────────────────────────────

class MissingClauseSchema(BaseModel):
    clause:      str    # "Termination", "Force Majeure", etc.
    status:      str    # "not_detected"
    importance:  str    # "high", "medium", "low"
    explanation: str    # why this might be important
    confidence:  float  # 0.0 - 1.0


class AmbiguousClauseSourceSchema(BaseModel):
    page_number: Optional[int] = None
    chunk_id:    str


class AmbiguousClauseSchema(BaseModel):
    issue_type:               str    # "ambiguous"
    clause:                   str    # "Payment", "Delivery", etc.
    text:                     str    # actual ambiguous text
    explanation:              str    # what's unclear
    suggested_clarification:  str    # how to clarify
    source:                   AmbiguousClauseSourceSchema


class ConflictingProvisionSchema(BaseModel):
    issue_type:   str    # "conflict"
    clause:       str    # "Payment Terms"
    text_1:       str    # first conflicting text
    text_2:       str    # second conflicting text
    explanation:  str    # nature of conflict
    source_1:     AmbiguousClauseSourceSchema
    source_2:     AmbiguousClauseSourceSchema


class MissingAmbiguousAnalysisSchema(BaseModel):
    document_type:            str    # detected type
    document_type_confidence: float  # 0.0 - 1.0
    missing_clauses:          List[MissingClauseSchema]
    ambiguous_clauses:        List[AmbiguousClauseSchema]
    conflicts:                List[ConflictingProvisionSchema]
    provider_used:            str


# ── Phase 6: Entities, Dates, Obligations, Evidence ──────────────────────────

class SourceReferenceSchema(BaseModel):
    """Source location in document"""
    page_number:   Optional[int]
    chunk_id:      str
    document_id:   Optional[int] = None
    document_name: Optional[str] = None


class PartySchema(BaseModel):
    """Extracted party with role"""
    name:     str
    role:     Optional[str]
    source:   SourceReferenceSchema
    evidence: Optional[str] = None


class KeyDateSchema(BaseModel):
    """Extracted date with type"""
    date:     str
    type:     str  # "Effective Date", "Start Date", etc.
    source:   SourceReferenceSchema
    evidence: Optional[str] = None


class EvidenceSchema(BaseModel):
    """Evidence quote with full source"""
    quote:         str
    document_id:   Optional[int]
    document_name: Optional[str]
    page_number:   Optional[int]
    chunk_id:      str


class EntitiesAnalysisSchema(BaseModel):
    """Complete entities extraction"""
    parties:      List[PartySchema]
    key_dates:    List[KeyDateSchema]
    obligations:  List[ObligationSchema]
    provider_used: str


class DocumentAnalysisResponse(BaseModel):
    document_id:         int
    filename:            str
    document_type:       str
    jurisdiction:        Optional[str] = None
    # Phase 2: structured summary (6 fields)
    structured_summary:  Optional[StructuredSummarySchema] = None
    # Phase 3: structured clauses and obligations
    structured_clauses:      Optional[List[ImportantClauseSchema]] = None
    structured_obligations:  Optional[List[ObligationSchema]]      = None
    # Phase 4: structured risk assessment
    structured_risk_assessment: Optional[RiskAssessmentSchema] = None
    # Phase 5: missing and ambiguous clause analysis
    structured_missing_ambiguous: Optional[MissingAmbiguousAnalysisSchema] = None
    # Phase 6: entities, dates, obligations with evidence
    structured_entities: Optional[EntitiesAnalysisSchema] = None
    # Legacy plain summary (mirrors executive_summary — kept for backward compat)
    summary:             str
    important_clauses:   List[str]
    risks:               List[str]
    missing_ambiguous:   List[str]
    key_dates:           List[str]
    parties:             List[str]
    obligations:         List[str]
    citations:           List[str]
    provider_used:       str
    analysis_successful: bool
    error_message:       Optional[str] = None
