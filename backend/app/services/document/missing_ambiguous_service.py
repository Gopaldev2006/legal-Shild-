"""
Missing and Ambiguous Clause Detection Service — Phase 5
========================================================
Detects potentially missing clauses, ambiguous language, and conflicting provisions.

IMPORTANT: Never states that a missing clause automatically makes a document illegal.
Uses language like "Not detected in the document."

Features
--------
1. Document Type Detection:
   - Identifies likely document type (Employment, NDA, Service Agreement, etc.)
   - Confidence scoring for type determination

2. Missing Clause Detection:
   - Configurable expected clause framework by document type
   - Not all clauses required for every document
   - Confidence scoring based on evidence

3. Ambiguous Language Detection:
   - Vague terms: "promptly", "reasonable", "as soon as possible"
   - Undefined timeframes
   - Unclear obligations

4. Conflict Detection:
   - Contradictory dates or deadlines
   - Conflicting payment terms
   - Inconsistent party references

Architecture
------------
- Gemini AI primary engine (contextual understanding)
- Rule-based fallback engine (pattern matching + heuristics)
- Document type-specific expected clause lists
- Evidence-based detection with source traceability

Security
--------
Caller must pass owner-scoped chunks only.
This service does NOT query the database.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set

from app.services.ai.gemini_service import GeminiService, get_gemini_api_key

logger = logging.getLogger(__name__)

MAX_TEXT_FOR_ANALYSIS = 15000  # chars


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class ClauseSource:
    page_number: Optional[int]
    chunk_id:    str


@dataclass
class MissingClause:
    clause:      str           # "Termination", "Force Majeure", etc.
    status:      str           # "not_detected"
    importance:  str           # "high", "medium", "low"
    explanation: str           # why this might be important
    confidence:  float         # 0.0 - 1.0


@dataclass
class AmbiguousClause:
    issue_type:               str           # "ambiguous"
    clause:                   str           # "Payment", "Delivery", etc.
    text:                     str           # actual ambiguous text
    explanation:              str           # what's unclear
    suggested_clarification:  str           # how to clarify
    source:                   ClauseSource


@dataclass
class ConflictingProvision:
    issue_type:   str           # "conflict"
    clause:       str           # "Payment Terms"
    text_1:       str           # first conflicting text
    text_2:       str           # second conflicting text
    explanation:  str           # nature of conflict
    source_1:     ClauseSource
    source_2:     ClauseSource


@dataclass
class MissingAmbiguousAnalysis:
    document_type:            str                                   # detected type
    document_type_confidence: float                                # 0.0 - 1.0
    missing_clauses:          List[MissingClause]          = field(default_factory=list)
    ambiguous_clauses:        List[AmbiguousClause]        = field(default_factory=list)
    conflicts:                List[ConflictingProvision]   = field(default_factory=list)
    provider_used:            str = "LexGuard Free Analysis Engine"
    analysis_successful:      bool = True
    error_message:            Optional[str] = None


# ── Document type detection ───────────────────────────────────────────────────

DOCUMENT_TYPES = {
    "Employment Agreement": {
        "keywords": ["employment", "employee", "employer", "job", "position", "hire", "salary", "wage"],
        "expected_clauses": [
            ("Parties", "high"),
            ("Employment Terms", "high"),
            ("Compensation", "high"),
            ("Term", "medium"),
            ("Termination", "high"),
            ("Confidentiality", "high"),
            ("Non-Compete", "medium"),
            ("Benefits", "medium"),
            ("Dispute Resolution", "medium"),
            ("Governing Law", "medium"),
        ],
    },
    "Service Agreement": {
        "keywords": ["services", "provider", "client", "consultant", "consulting", "deliverables"],
        "expected_clauses": [
            ("Parties", "high"),
            ("Scope of Services", "high"),
            ("Payment Terms", "high"),
            ("Term", "medium"),
            ("Termination", "high"),
            ("Intellectual Property", "high"),
            ("Liability", "high"),
            ("Confidentiality", "medium"),
            ("Dispute Resolution", "medium"),
            ("Governing Law", "medium"),
        ],
    },
    "Non-Disclosure Agreement": {
        "keywords": ["confidential", "proprietary", "non-disclosure", "nda", "secret"],
        "expected_clauses": [
            ("Parties", "high"),
            ("Definitions", "high"),
            ("Confidential Information", "high"),
            ("Obligations", "high"),
            ("Term", "medium"),
            ("Exceptions", "medium"),
            ("Return of Materials", "medium"),
            ("Remedies", "medium"),
            ("Governing Law", "low"),
        ],
    },
    "Lease Agreement": {
        "keywords": ["lease", "rent", "tenant", "landlord", "premises", "property"],
        "expected_clauses": [
            ("Parties", "high"),
            ("Premises Description", "high"),
            ("Term", "high"),
            ("Rent", "high"),
            ("Security Deposit", "high"),
            ("Maintenance", "medium"),
            ("Termination", "high"),
            ("Default", "medium"),
            ("Dispute Resolution", "medium"),
        ],
    },
    "Sale Agreement": {
        "keywords": ["sale", "purchase", "buyer", "seller", "goods", "product"],
        "expected_clauses": [
            ("Parties", "high"),
            ("Subject Matter", "high"),
            ("Purchase Price", "high"),
            ("Payment Terms", "high"),
            ("Delivery", "high"),
            ("Warranties", "high"),
            ("Liability", "medium"),
            ("Termination", "medium"),
            ("Governing Law", "medium"),
        ],
    },
    "Loan Agreement": {
        "keywords": ["loan", "lender", "borrower", "principal", "interest", "repayment"],
        "expected_clauses": [
            ("Parties", "high"),
            ("Loan Amount", "high"),
            ("Interest Rate", "high"),
            ("Repayment Terms", "high"),
            ("Security/Collateral", "high"),
            ("Default", "high"),
            ("Acceleration", "medium"),
            ("Governing Law", "medium"),
        ],
    },
    "General Contract": {
        "keywords": ["agreement", "contract", "parties", "terms", "conditions"],
        "expected_clauses": [
            ("Parties", "high"),
            ("Definitions", "medium"),
            ("Scope", "high"),
            ("Payment Terms", "high"),
            ("Term", "medium"),
            ("Termination", "high"),
            ("Liability", "medium"),
            ("Dispute Resolution", "medium"),
            ("Governing Law", "medium"),
        ],
    },
}


def _detect_document_type(text: str) -> tuple[str, float]:
    """
    Detect document type based on keywords.
    Returns (type_name, confidence_score).
    """
    text_lower = text.lower()
    
    scores = {}
    for doc_type, config in DOCUMENT_TYPES.items():
        keyword_count = sum(1 for kw in config["keywords"] if kw in text_lower)
        score = keyword_count / len(config["keywords"])
        scores[doc_type] = score
    
    if not scores:
        return "General Contract", 0.5
    
    best_type = max(scores.items(), key=lambda x: x[1])
    
    # If score is too low, fall back to General Contract
    if best_type[1] < 0.15:
        return "General Contract", 0.5
    
    # Confidence based on score
    confidence = min(1.0, best_type[1] * 2.0)  # scale up
    
    return best_type[0], confidence


# ── Ambiguous language patterns ───────────────────────────────────────────────

AMBIGUOUS_TERMS = {
    "vague_timeframe": {
        "patterns": [
            r"\bpromptly\b",
            r"\bas soon as (?:possible|practicable)\b",
            r"\breasonable time\b",
            r"\bin due course\b",
            r"\bwithout delay\b",
            r"\btimely manner\b",
        ],
        "explanation": "Timeframe is not specifically defined",
        "clarification": "Specify exact timeframe (e.g., 'within 30 days')",
    },
    "vague_quantity": {
        "patterns": [
            r"\breasonable (?:amount|number|quantity)\b",
            r"\badequate (?:amount|number|quantity)\b",
            r"\bsufficient (?:amount|number|quantity)\b",
        ],
        "explanation": "Quantity or amount is not specifically defined",
        "clarification": "Specify exact quantity or range (e.g., 'at least 100 units')",
    },
    "vague_quality": {
        "patterns": [
            r"\breasonable quality\b",
            r"\bacceptable quality\b",
            r"\bsatisfactory (?:quality|performance)\b",
            r"\bappropriate standard\b",
        ],
        "explanation": "Quality standard is not specifically defined",
        "clarification": "Specify measurable quality criteria or reference standard",
    },
    "vague_effort": {
        "patterns": [
            r"\bbest efforts\b",
            r"\breasonable efforts\b",
            r"\bcommercially reasonable efforts\b",
            r"\bgood faith efforts\b",
        ],
        "explanation": "Effort level is subjective and may lead to disputes",
        "clarification": "Define specific actions or milestones",
    },
    "vague_condition": {
        "patterns": [
            r"\bif appropriate\b",
            r"\bif necessary\b",
            r"\bif required\b",
            r"\bas deemed necessary\b",
        ],
        "explanation": "Condition is subjective without defined criteria",
        "clarification": "Specify objective criteria for when condition applies",
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_valid_gemini_key(key: str) -> bool:
    return bool(key) and key.startswith("AIzaSy")


def _parse_json_response(raw: str) -> Optional[Dict[str, Any]]:
    """Robustly extract JSON from Gemini response."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:] if len(lines) > 2 else lines
        text  = "\n".join(inner[:-1] if inner and inner[-1].strip() == "```" else inner)
    try:
        return json.loads(text.strip())
    except Exception:
        try:
            start = text.index("{")
            end   = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return None


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are LexGuard AI, an expert legal document analyst. "
    "You identify missing clauses, ambiguous language, and conflicting provisions. "
    "You return valid JSON only. Never state that a missing clause makes a document illegal. "
    "Use language like 'Not detected in the document'."
)


def _analysis_prompt(filename: str, doc_type: str, text: str) -> str:
    return f"""You are LexGuard AI. Analyze the legal document for missing clauses, ambiguous language, and conflicts.

Return EXACTLY this JSON structure:
{{
  "missing_clauses": [
    {{
      "clause": "Termination",
      "status": "not_detected",
      "importance": "high",
      "explanation": "Termination provisions not detected; parties may lack clarity on exit procedures",
      "confidence": 0.78
    }}
  ],
  "ambiguous_clauses": [
    {{
      "issue_type": "ambiguous",
      "clause": "Payment",
      "text": "Payment will be made promptly",
      "explanation": "Promptly does not define a specific deadline",
      "suggested_clarification": "Specify exact timeframe (e.g., within 30 days)"
    }}
  ],
  "conflicts": [
    {{
      "issue_type": "conflict",
      "clause": "Payment Terms",
      "text_1": "Payment due in 15 days",
      "text_2": "Payment due in 30 days",
      "explanation": "Document contains conflicting payment deadlines"
    }}
  ]
}}

CRITICAL RULES:
1. Return ONLY valid JSON. No markdown, no explanation outside JSON.
2. For missing clauses: use status "not_detected" (never "illegal" or "required").
3. Importance: "high", "medium", or "low".
4. Confidence: 0.0 (uncertain) to 1.0 (highly confident).
5. For ambiguous clauses: quote exact text, explain issue, suggest clarification.
6. For conflicts: provide both conflicting texts with explanation.
7. Focus on actual document content, not hypotheticals.

DOCUMENT METADATA:
Filename: {filename}
Document Type: {doc_type}

DOCUMENT TEXT:
{text}

Return JSON now:"""


# ── Gemini analysis ───────────────────────────────────────────────────────────

def _gemini_analysis(gemini: GeminiService, filename: str, doc_type: str, text: str) -> Optional[Dict]:
    """Use Gemini to analyze missing/ambiguous clauses."""
    raw = gemini.generate_response(
        prompt=             _analysis_prompt(filename, doc_type, text),
        system_instruction= _SYSTEM_PROMPT,
        temperature=        0.2,
    )
    if not raw or raw.startswith("[Google Gemini API Error"):
        return None
    return _parse_json_response(raw)


# ── Free engine analysis ──────────────────────────────────────────────────────

def _free_engine_analysis(
    filename: str,
    detected_type: str,
    text: str,
    chunks: List[Dict]
) -> MissingAmbiguousAnalysis:
    """
    Rule-based missing/ambiguous clause detection.
    """
    text_lower = text.lower()
    
    # Get expected clauses for detected type
    type_config = DOCUMENT_TYPES.get(detected_type, DOCUMENT_TYPES["General Contract"])
    expected_clauses = type_config["expected_clauses"]
    
    missing_clauses = []
    ambiguous_clauses = []
    conflicts = []
    
    # ── Missing Clause Detection ──────────────────────────────────────────
    for clause_name, importance in expected_clauses:
        # Check if clause exists
        clause_keywords = clause_name.lower().split()
        found = any(kw in text_lower for kw in clause_keywords)
        
        if not found:
            # Additional check for common variations
            variations = {
                "Termination": ["terminate", "cancel", "end"],
                "Payment Terms": ["payment", "pay", "compensation"],
                "Confidentiality": ["confidential", "non-disclosure", "secret"],
                "Liability": ["liable", "liability", "damages"],
                "Dispute Resolution": ["dispute", "arbitration", "mediation"],
                "Governing Law": ["governed by", "laws of", "jurisdiction"],
            }
            
            if clause_name in variations:
                found = any(var in text_lower for var in variations[clause_name])
        
        if not found:
            explanations = {
                "Termination": "Termination provisions not detected; parties may lack clarity on how to exit the agreement",
                "Payment Terms": "Payment terms not detected; unclear when and how payment should be made",
                "Confidentiality": "Confidentiality provisions not detected; sensitive information may lack protection",
                "Liability": "Liability provisions not detected; exposure to claims may be unclear",
                "Dispute Resolution": "Dispute resolution mechanism not detected; unclear how disputes will be handled",
                "Governing Law": "Governing law not specified; legal framework for interpretation unclear",
                "Intellectual Property": "IP rights provisions not detected; ownership may be ambiguous",
                "Force Majeure": "Force majeure clause not detected; no protection for unforeseeable events",
            }
            
            explanation = explanations.get(clause_name, 
                f"{clause_name} provisions not detected in the document")
            
            missing_clauses.append(MissingClause(
                clause=      clause_name,
                status=      "not_detected",
                importance=  importance,
                explanation= explanation,
                confidence=  0.75 if importance == "high" else 0.65,
            ))
    
    # ── Ambiguous Language Detection ──────────────────────────────────────
    for category, config in AMBIGUOUS_TERMS.items():
        for pattern in config["patterns"]:
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            for match in matches[:3]:  # limit to 3 per category
                # Find source chunk
                match_pos = match.start()
                source_chunk = chunks[0]
                cumulative_pos = 0
                for chunk in chunks:
                    chunk_len = len(chunk["text"])
                    if cumulative_pos <= match_pos < cumulative_pos + chunk_len:
                        source_chunk = chunk
                        break
                    cumulative_pos += chunk_len
                
                # Extract context
                start = max(0, match_pos - 50)
                end = min(len(text), match_pos + 100)
                context = text[start:end].strip()
                
                # Determine clause type
                clause_type = "General"
                if "payment" in context.lower() or "pay" in context.lower():
                    clause_type = "Payment"
                elif "deliver" in context.lower():
                    clause_type = "Delivery"
                elif "notice" in context.lower():
                    clause_type = "Notice"
                elif "perform" in context.lower():
                    clause_type = "Performance"
                
                ambiguous_clauses.append(AmbiguousClause(
                    issue_type=              "ambiguous",
                    clause=                  clause_type,
                    text=                    context[:200],
                    explanation=             config["explanation"],
                    suggested_clarification= config["clarification"],
                    source=                  ClauseSource(
                        page_number= source_chunk.get("page_number"),
                        chunk_id=    source_chunk["chunk_id"],
                    )
                ))
    
    # ── Conflict Detection ────────────────────────────────────────────────
    # Detect conflicting dates/numbers
    date_patterns = [
        (r'(\d+)\s+(?:days?|business\s+days?)', "days"),
        (r'(\d+)\s+(?:months?)', "months"),
        (r'(\d+)%', "percentage"),
    ]
    
    for pattern, unit in date_patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if len(matches) >= 2:
            # Check if they're in similar contexts (potential conflict)
            for i, m1 in enumerate(matches):
                for m2 in matches[i+1:i+3]:  # check next 2 matches
                    num1 = int(m1.group(1))
                    num2 = int(m2.group(1))
                    
                    # Potential conflict if numbers differ significantly
                    if abs(num1 - num2) > (max(num1, num2) * 0.3):  # 30% difference
                        # Extract context
                        ctx1_start = max(0, m1.start() - 50)
                        ctx1_end = min(len(text), m1.end() + 50)
                        context1 = text[ctx1_start:ctx1_end].strip()
                        
                        ctx2_start = max(0, m2.start() - 50)
                        ctx2_end = min(len(text), m2.end() + 50)
                        context2 = text[ctx2_start:ctx2_end].strip()
                        
                        # Find source chunks
                        source1 = chunks[0]
                        source2 = chunks[0]
                        
                        cumulative = 0
                        for chunk in chunks:
                            if cumulative <= m1.start() < cumulative + len(chunk["text"]):
                                source1 = chunk
                            if cumulative <= m2.start() < cumulative + len(chunk["text"]):
                                source2 = chunk
                            cumulative += len(chunk["text"])
                        
                        conflicts.append(ConflictingProvision(
                            issue_type=  "conflict",
                            clause=      f"Terms ({unit})",
                            text_1=      context1[:150],
                            text_2=      context2[:150],
                            explanation= f"Document contains potentially conflicting {unit} values: {num1} vs {num2}",
                            source_1=    ClauseSource(
                                page_number= source1.get("page_number"),
                                chunk_id=    source1["chunk_id"],
                            ),
                            source_2=    ClauseSource(
                                page_number= source2.get("page_number"),
                                chunk_id=    source2["chunk_id"],
                            ),
                        ))
                        break  # Only report first conflict per pair
    
    # Limit results
    missing_clauses = missing_clauses[:8]
    ambiguous_clauses = ambiguous_clauses[:10]
    conflicts = conflicts[:5]
    
    return missing_clauses, ambiguous_clauses, conflicts


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_missing_ambiguous(
    filename:    str,
    doc_type:    str,
    jurisdiction: Optional[str],
    chunks:      List[Dict],  # [{"text": str, "chunk_id": str, "page_number": int|None}]
) -> MissingAmbiguousAnalysis:
    """
    Detect missing clauses, ambiguous language, and conflicting provisions.
    
    Parameters
    ----------
    filename     : original document filename
    doc_type     : DocumentType.value string (may be overridden by detection)
    jurisdiction : optional jurisdiction
    chunks       : list of dicts with keys: text, chunk_id, page_number
    
    Returns
    -------
    MissingAmbiguousAnalysis with detected type, missing clauses, ambiguous clauses, conflicts
    """
    if not chunks:
        return MissingAmbiguousAnalysis(
            document_type=            "Unknown",
            document_type_confidence= 0.0,
            missing_clauses=          [],
            ambiguous_clauses=        [],
            conflicts=                [],
            analysis_successful=      False,
            error_message=            "No text chunks available for analysis",
        )
    
    full_text = "\n\n".join(c["text"] for c in chunks)[:MAX_TEXT_FOR_ANALYSIS]
    
    # ── Detect document type ──────────────────────────────────────────────
    detected_type, type_confidence = _detect_document_type(full_text)
    
    # ── Try Gemini ─────────────────────────────────────────────────────────
    api_key = get_gemini_api_key()
    if _is_valid_gemini_key(api_key):
        try:
            gemini = GeminiService(api_key=api_key)
            parsed = _gemini_analysis(gemini, filename, detected_type, full_text)
            
            if parsed:
                # Build structured results from Gemini response
                missing_objs = []
                for m_dict in parsed.get("missing_clauses", []):
                    missing_objs.append(MissingClause(
                        clause=      m_dict.get("clause", "Unknown"),
                        status=      "not_detected",
                        importance=  m_dict.get("importance", "medium"),
                        explanation= m_dict.get("explanation", ""),
                        confidence=  m_dict.get("confidence", 0.75),
                    ))
                
                ambiguous_objs = []
                for a_dict in parsed.get("ambiguous_clauses", []):
                    # Find best matching chunk
                    text_snippet = a_dict.get("text", "").lower()
                    best_chunk = chunks[0]
                    for chunk in chunks:
                        if any(word in chunk["text"].lower() for word in text_snippet.split()[:5]):
                            best_chunk = chunk
                            break
                    
                    ambiguous_objs.append(AmbiguousClause(
                        issue_type=              "ambiguous",
                        clause=                  a_dict.get("clause", "General"),
                        text=                    a_dict.get("text", "")[:300],
                        explanation=             a_dict.get("explanation", ""),
                        suggested_clarification= a_dict.get("suggested_clarification", ""),
                        source=                  ClauseSource(
                            page_number= best_chunk.get("page_number"),
                            chunk_id=    best_chunk["chunk_id"],
                        )
                    ))
                
                conflict_objs = []
                for c_dict in parsed.get("conflicts", []):
                    # Find chunks for both texts
                    text1 = c_dict.get("text_1", "").lower()
                    text2 = c_dict.get("text_2", "").lower()
                    
                    chunk1 = chunks[0]
                    chunk2 = chunks[0]
                    
                    for chunk in chunks:
                        chunk_lower = chunk["text"].lower()
                        if any(word in chunk_lower for word in text1.split()[:5]):
                            chunk1 = chunk
                        if any(word in chunk_lower for word in text2.split()[:5]):
                            chunk2 = chunk
                    
                    conflict_objs.append(ConflictingProvision(
                        issue_type=  "conflict",
                        clause=      c_dict.get("clause", "General"),
                        text_1=      c_dict.get("text_1", "")[:200],
                        text_2=      c_dict.get("text_2", "")[:200],
                        explanation= c_dict.get("explanation", ""),
                        source_1=    ClauseSource(
                            page_number= chunk1.get("page_number"),
                            chunk_id=    chunk1["chunk_id"],
                        ),
                        source_2=    ClauseSource(
                            page_number= chunk2.get("page_number"),
                            chunk_id=    chunk2["chunk_id"],
                        ),
                    ))
                
                return MissingAmbiguousAnalysis(
                    document_type=            detected_type,
                    document_type_confidence= type_confidence,
                    missing_clauses=          missing_objs[:10],
                    ambiguous_clauses=        ambiguous_objs[:10],
                    conflicts=                conflict_objs[:5],
                    provider_used=            "Google Gemini AI",
                    analysis_successful=      True,
                )
        
        except Exception as exc:
            logger.warning("Gemini missing/ambiguous analysis failed: %s", exc)
    
    # ── Fallback — rule-based engine ───────────────────────────────────────
    missing, ambiguous, conflicts = _free_engine_analysis(filename, detected_type, full_text, chunks)
    
    return MissingAmbiguousAnalysis(
        document_type=            detected_type,
        document_type_confidence= type_confidence,
        missing_clauses=          missing,
        ambiguous_clauses=        ambiguous,
        conflicts=                conflicts,
        provider_used=            "LexGuard Free Analysis Engine",
        analysis_successful=      True,
    )
