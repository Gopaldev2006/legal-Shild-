"""
Document Analysis Engine
========================
Produces a structured 8-section legal analysis of an uploaded document
plus a Phase 2 structured summary (6 fields: executive_summary, document_type,
purpose, main_subject, key_takeaways, sources).

Sections
--------
1. Structured Summary   — Phase 2: 6-field hierarchical summary
2. Important Clauses    — key contractual / statutory provisions
3. Risk Identification  — potential legal risks for each party
4. Missing / Ambiguous  — absent or vague clauses
5. Key Dates            — deadlines, notice periods, effective dates
6. Parties              — names, roles
7. Obligations          — what each party must do / must not do
8. Evidence / Citations — statutes, case law, clause references

Security
--------
Only chunks owned by current_user.id are used.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.document import LegalDocument, DocumentChunk
from app.models.user import UserRole
from app.services.ai.gemini_service import GeminiService, get_gemini_api_key
from app.services.document.summary_service import summarize_document, SummaryResult
from app.services.document.clause_analysis_service import (
    analyze_clauses_and_obligations,
    ClauseAnalysisResult,
)
from app.services.document.risk_analysis_service import (
    analyze_legal_risks,
    RiskAssessment,
)
from app.services.document.missing_ambiguous_service import (
    analyze_missing_ambiguous,
    MissingAmbiguousAnalysis,
)
from app.services.document.entities_extraction_service import (
    extract_entities,
    EntitiesAnalysis,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "\n\n---\n*Legal Disclaimer: This analysis is AI-generated for informational "
    "purposes only and does not constitute formal legal advice. "
    "Consult a qualified legal professional for case-specific guidance.*"
)

MAX_ANALYSIS_CHARS = 12000   # protect Gemini context window


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class DocumentAnalysis:
    document_id:         int
    filename:            str
    document_type:       str
    jurisdiction:        Optional[str]
    # Phase 2: structured 6-field summary (replaces plain string summary)
    structured_summary:  Optional[SummaryResult]  = None
    # Phase 3: structured clause analysis
    clause_analysis:     Optional[ClauseAnalysisResult] = None
    # Phase 4: structured risk assessment
    risk_assessment:     Optional[RiskAssessment] = None
    # Phase 5: missing and ambiguous clause analysis
    missing_ambiguous_analysis: Optional[MissingAmbiguousAnalysis] = None
    # Phase 6: entities extraction (parties, dates, obligations with evidence)
    entities_analysis: Optional[EntitiesAnalysis] = None
    # Legacy plain summary (kept for backward compat — mirrors executive_summary)
    summary:             str              = ""
    important_clauses:   List[str]        = field(default_factory=list)
    risks:               List[str]        = field(default_factory=list)
    missing_ambiguous:   List[str]        = field(default_factory=list)
    key_dates:           List[str]        = field(default_factory=list)
    parties:             List[str]        = field(default_factory=list)
    obligations:         List[str]        = field(default_factory=list)
    citations:           List[str]        = field(default_factory=list)
    provider_used:       str              = "Free Analysis Engine"
    analysis_successful: bool             = True
    error_message:       Optional[str]    = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_valid_gemini_key(key: str) -> bool:
    return bool(key) and key.startswith("AIzaSy")


def _collect_document_text(document_id: int, user_id: int,
                            user_role: str, db: Session) -> str:
    """Collect all chunk text for this document, owner-scoped."""
    q = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    )
    if user_role != UserRole.ADMIN.value:
        q = q.filter(DocumentChunk.owner_id == user_id)

    chunks = q.order_by(DocumentChunk.chunk_index.asc()).all()
    full_text = "\n\n".join(c.text for c in chunks if c.text.strip())
    return full_text[:MAX_ANALYSIS_CHARS]


def _collect_chunks(document_id: int, user_id: int,
                    user_role: str, db: Session) -> List[Dict[str, Any]]:
    """
    Return owner-scoped chunks as plain dicts suitable for summary_service.
    Each dict: {"text": str, "chunk_id": str, "page_number": int|None}
    """
    q = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    )
    if user_role != UserRole.ADMIN.value:
        q = q.filter(DocumentChunk.owner_id == user_id)

    rows = q.order_by(DocumentChunk.chunk_index.asc()).all()
    return [
        {
            "text":        c.text,
            "chunk_id":    c.chunk_id,
            "page_number": c.page_number,
        }
        for c in rows if c.text.strip()
    ]


def _build_analysis_prompt(filename: str, doc_type: str,
                            jurisdiction: Optional[str], text: str) -> str:
    ctx = f"Filename: {filename}\nDocument Type: {doc_type}"
    if jurisdiction:
        ctx += f"\nJurisdiction: {jurisdiction}"

    return f"""You are LexGuard AI, an expert legal document analyst.

Analyse the following legal document and return a structured JSON response with EXACTLY these 8 keys:

{{
  "summary": "2-3 sentence plain-English overview of the document",
  "important_clauses": ["clause 1 description", "clause 2 description", ...],
  "risks": ["risk 1 for party X", "risk 2 for party Y", ...],
  "missing_ambiguous": ["missing clause 1", "ambiguous provision 1", ...],
  "key_dates": ["date/deadline 1", "date/deadline 2", ...],
  "parties": ["Party A: name and role", "Party B: name and role", ...],
  "obligations": ["Party A must...", "Party B must not...", ...],
  "citations": ["Section X of Act Y", "Clause Z reference", ...]
}}

RULES:
- Return ONLY valid JSON. No markdown, no explanation outside the JSON.
- Base every point on the document text provided. Do NOT invent clauses.
- If a section has no relevant content, return an empty list [] or empty string "".
- For risks: identify specific legal risks (ambiguity, missing terms, liability gaps).
- For missing/ambiguous: flag vague language, undefined terms, absent standard clauses.
- For citations: reference specific clause numbers, section numbers, or applicable laws found in the text.
- Keep each list item concise (1-2 sentences max).

DOCUMENT METADATA:
{ctx}

DOCUMENT TEXT:
{text}

Return the JSON analysis now:"""


def _build_analysis_system_prompt() -> str:
    return (
        "You are LexGuard AI, a professional legal document analyst. "
        "You extract structured insights from legal documents. "
        "Always return valid JSON. Never invent facts not present in the document. "
        "Be precise, professional, and concise."
    )


def _parse_gemini_json(raw: str) -> Optional[dict]:
    """Extract and parse JSON from Gemini response."""
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        return json.loads(text)
    except Exception:
        # Try to find JSON object in the response
        try:
            start = raw.index("{")
            end   = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except Exception:
            return None


def _free_engine_analysis(filename: str, text: str) -> DocumentAnalysis:
    """
    Rule-based fallback when Gemini is unavailable.
    Extracts structured info using keyword patterns.
    """
    import re

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    lower = text.lower()

    # ── Summary ───────────────────────────────────────────────────────────
    first_para = " ".join(lines[:5])[:400]
    summary = f"This document appears to be a {filename.rsplit('.',1)[0].replace('_',' ').title()}. " \
              f"{first_para[:200]}{'...' if len(first_para) > 200 else ''}"

    # ── Parties ───────────────────────────────────────────────────────────
    party_patterns = [
        r'between\s+([A-Z][^,\n]+?)\s+(?:and|&)\s+([A-Z][^,\n]+?)[\.,\n]',
        r'"([A-Z][a-zA-Z\s]+?)"\s*\("(?:Client|Provider|Employer|Employee|Vendor|Buyer|Seller|Party [AB])"\)',
    ]
    parties = []
    for pat in party_patterns:
        for m in re.finditer(pat, text):
            for g in m.groups():
                if g and len(g.strip()) > 2:
                    parties.append(g.strip())
    parties = list(dict.fromkeys(parties))[:6]
    if not parties:
        parties = ["Parties not clearly identified — review document manually"]

    # ── Important Clauses ─────────────────────────────────────────────────
    clause_keywords = ["terminat", "confidential", "payment", "liabilit",
                       "indemnif", "warrant", "govern", "arbitrat", "non-compete"]
    important_clauses = []
    for kw in clause_keywords:
        for line in lines:
            if kw in line.lower() and len(line) > 20:
                important_clauses.append(line[:200])
                break
    if not important_clauses:
        important_clauses = ["No standard clauses detected automatically — review document manually"]

    # ── Key Dates ─────────────────────────────────────────────────────────
    date_patterns = [
        r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',
        r'\b(?:within|after|before)\s+\d+\s+(?:days?|months?|years?)\b',
        r'\b\d+\s+days?\s+(?:written\s+)?notice\b',
    ]
    key_dates = []
    for pat in date_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            # Get surrounding context
            start = max(0, m.start() - 30)
            snippet = text[start: m.end() + 60].strip().replace("\n", " ")
            if snippet not in key_dates:
                key_dates.append(snippet[:150])
    key_dates = key_dates[:8]
    if not key_dates:
        key_dates = ["No specific dates identified — review document manually"]

    # ── Obligations ───────────────────────────────────────────────────────
    obligation_keywords = ["shall", "must", "agrees to", "required to", "obliged to",
                           "shall not", "must not", "prohibited"]
    obligations = []
    for line in lines:
        if any(kw in line.lower() for kw in obligation_keywords) and len(line) > 20:
            obligations.append(line[:200])
        if len(obligations) >= 8:
            break
    if not obligations:
        obligations = ["Obligations not clearly parsed — review full document"]

    # ── Risks ─────────────────────────────────────────────────────────────
    risks = []
    if "terminat" in lower:
        risks.append("Termination clause present — verify notice periods and grounds are clearly defined")
    if "liabilit" in lower:
        risks.append("Liability provisions found — check caps, exclusions, and indemnification scope")
    if "confidential" not in lower:
        risks.append("No confidentiality clause detected — proprietary information may be unprotected")
    if "arbitrat" not in lower and "jurisdict" not in lower:
        risks.append("Dispute resolution mechanism not found — parties may face jurisdictional uncertainty")
    if "non-compete" in lower or "non compete" in lower:
        risks.append("Non-compete clause present — verify enforceability under applicable law")
    if not risks:
        risks = ["No obvious risks detected automatically — manual legal review recommended"]

    # ── Missing / Ambiguous ───────────────────────────────────────────────
    missing = []
    standard_clauses = {
        "force majeure":  "Force Majeure clause",
        "governing law":  "Governing Law clause",
        "confidential":   "Confidentiality / NDA clause",
        "arbitrat":       "Dispute Resolution / Arbitration clause",
        "terminat":       "Termination clause",
        "indemnif":       "Indemnification clause",
        "intellectual property": "Intellectual Property clause",
    }
    for keyword, label in standard_clauses.items():
        if keyword not in lower:
            missing.append(f"Missing: {label}")
    if not missing:
        missing = ["All standard clauses appear to be present"]

    # ── Citations ─────────────────────────────────────────────────────────
    citation_patterns = [
        r'(?:Section|Clause|Article|Schedule)\s+\d+[\.\d]*[A-Z]?',
        r'(?:Act|Code|Regulation|Rules?)\s+\d{4}',
        r'IPC|CrPC|CPC|ICA|SEBI|RERA|GST',
    ]
    citations = []
    for pat in citation_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            c = m.group().strip()
            if c not in citations:
                citations.append(c)
    citations = citations[:10]
    if not citations:
        citations = ["No specific statutory citations found in text"]

    return DocumentAnalysis(
        document_id=0,
        filename=filename,
        document_type="",
        jurisdiction=None,
        summary=summary,
        important_clauses=important_clauses[:8],
        risks=risks[:6],
        missing_ambiguous=missing[:8],
        key_dates=key_dates[:8],
        parties=parties[:6],
        obligations=obligations[:8],
        citations=citations[:10],
        provider_used="LexGuard Free Analysis Engine",
        analysis_successful=True,
    )


# ── main function ─────────────────────────────────────────────────────────────

def analyze_document(
    document_id: int,
    user_id:     int,
    user_role:   str,
    db:          Session,
) -> DocumentAnalysis:
    """
    Produces a structured analysis of the specified document.
    Phase 2: includes structured_summary (6-field hierarchical summary).
    Ownership enforced — only the document owner (or ADMIN) can analyse.
    """
    # Load document metadata
    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not doc:
        return DocumentAnalysis(
            document_id=document_id, filename="Unknown", document_type="",
            jurisdiction=None, summary="Document not found.",
            analysis_successful=False, error_message="Document not found",
        )

    # Collect chunks (used by both summarizer and analysis engine)
    chunk_dicts = _collect_chunks(document_id, user_id, user_role, db)
    full_text   = "\n\n".join(c["text"] for c in chunk_dicts)[:MAX_ANALYSIS_CHARS]

    if not full_text.strip():
        return DocumentAnalysis(
            document_id=document_id,
            filename=doc.filename,
            document_type=doc.document_type.value,
            jurisdiction=doc.jurisdiction,
            summary="Document has no extractable text. Please reprocess the document.",
            analysis_successful=False,
            error_message="No text content available",
        )

    # ── Phase 2: Run structured summarization first ───────────────────────
    structured_summary = summarize_document(
        filename=    doc.filename,
        doc_type=    doc.document_type.value,
        jurisdiction=doc.jurisdiction,
        chunks=      chunk_dicts,
    )

    # ── Phase 3: Run clause and obligation analysis ───────────────────────
    clause_analysis = analyze_clauses_and_obligations(
        filename=    doc.filename,
        doc_type=    doc.document_type.value,
        jurisdiction=doc.jurisdiction,
        chunks=      chunk_dicts,
    )

    # ── Phase 4: Run legal risk analysis ──────────────────────────────────
    risk_assessment = analyze_legal_risks(
        filename=    doc.filename,
        doc_type=    doc.document_type.value,
        jurisdiction=doc.jurisdiction,
        chunks=      chunk_dicts,
    )

    # ── Phase 5: Run missing/ambiguous clause analysis ────────────────────
    missing_ambiguous_analysis = analyze_missing_ambiguous(
        filename=    doc.filename,
        doc_type=    doc.document_type.value,
        jurisdiction=doc.jurisdiction,
        chunks=      chunk_dicts,
    )

    # ── Phase 6: Extract entities (parties, dates, obligations) ───────────
    entities_analysis = extract_entities(
        filename=    doc.filename,
        document_id= document_id,
        chunks=      chunk_dicts,
    )

    # ── Try Gemini for full 8-section analysis ────────────────────────────
    api_key = get_gemini_api_key()
    if _is_valid_gemini_key(api_key):
        try:
            system_prompt = _build_analysis_system_prompt()
            user_prompt   = _build_analysis_prompt(
                doc.filename, doc.document_type.value,
                doc.jurisdiction, full_text
            )
            gemini   = GeminiService(api_key=api_key)
            raw_resp = gemini.generate_response(
                prompt=             user_prompt,
                system_instruction= system_prompt,
                temperature=        0.1,
            )
            if raw_resp and not raw_resp.startswith("[Google Gemini API Error"):
                parsed = _parse_gemini_json(raw_resp)
                if parsed:
                    return DocumentAnalysis(
                        document_id=       document_id,
                        filename=          doc.filename,
                        document_type=     doc.document_type.value,
                        jurisdiction=      doc.jurisdiction,
                        structured_summary=structured_summary,
                        clause_analysis=   clause_analysis,
                        risk_assessment=   risk_assessment,
                        missing_ambiguous_analysis= missing_ambiguous_analysis,
                        entities_analysis= entities_analysis,
                        summary=           structured_summary.executive_summary,
                        important_clauses= parsed.get("important_clauses", []),
                        risks=             parsed.get("risks", []),
                        missing_ambiguous= parsed.get("missing_ambiguous", []),
                        key_dates=         parsed.get("key_dates", []),
                        parties=           parsed.get("parties", []),
                        obligations=       parsed.get("obligations", []),
                        citations=         parsed.get("citations", []),
                        provider_used=     structured_summary.provider_used,
                        analysis_successful=True,
                    )
        except Exception as exc:
            logger.warning("Gemini analysis failed: %s", exc)

    # ── Fallback — rule-based engine ──────────────────────────────────────
    result = _free_engine_analysis(doc.filename, full_text)
    result.document_id        = document_id
    result.document_type      = doc.document_type.value
    result.jurisdiction       = doc.jurisdiction
    result.structured_summary = structured_summary
    result.clause_analysis    = clause_analysis
    result.risk_assessment    = risk_assessment
    result.missing_ambiguous_analysis = missing_ambiguous_analysis
    result.entities_analysis  = entities_analysis
    result.summary            = structured_summary.executive_summary
    return result
