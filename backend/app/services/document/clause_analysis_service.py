"""
Clause Analysis Service — Phase 3
===================================
Extracts and classifies important legal clauses and obligations from documents.

Features
--------
1. Clause Extraction:
   - Identifies 19+ standard clause types (Payment, Termination, Confidentiality, etc.)
   - Classifies importance: high, medium, low
   - Provides description and source references

2. Obligations Extraction:
   - Identifies party-specific obligations
   - Extracts deadlines when present
   - Links to source chunks

Architecture
------------
- Gemini AI primary engine (when valid API key available)
- Rule-based fallback engine (regex + keyword patterns)
- Reuses existing chunk retrieval system
- Source traceability for all findings

Security
--------
Caller must pass owner-scoped chunks only.
This service does NOT query the database.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from app.services.ai.gemini_service import GeminiService, get_gemini_api_key

logger = logging.getLogger(__name__)

MAX_TEXT_FOR_CLAUSE_ANALYSIS = 15000  # chars


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class ClauseSource:
    page_number: Optional[int]
    chunk_id:    str


@dataclass
class ImportantClause:
    clause_type: str           # "Termination", "Payment", "Confidentiality", etc.
    title:       str           # human-readable title
    description: str           # explanation of what the clause says
    importance:  str           # "high", "medium", "low"
    source:      ClauseSource  # page_number, chunk_id


@dataclass
class Obligation:
    party:      str              # "Employee", "Client", "Provider", etc.
    obligation: str              # what the party must do/not do
    deadline:   str              # "Within 30 days", "Not specified", etc.
    source:     ClauseSource


@dataclass
class ClauseAnalysisResult:
    clauses:            List[ImportantClause] = field(default_factory=list)
    obligations:        List[Obligation]      = field(default_factory=list)
    provider_used:      str                   = "LexGuard Free Clause Engine"
    analysis_successful: bool                 = True
    error_message:      Optional[str]         = None


# ── Standard clause types ─────────────────────────────────────────────────────

STANDARD_CLAUSE_TYPES = [
    "Definitions",
    "Payment",
    "Term",
    "Renewal",
    "Termination",
    "Confidentiality",
    "Privacy",
    "Intellectual Property",
    "Liability",
    "Indemnification",
    "Dispute Resolution",
    "Arbitration",
    "Jurisdiction",
    "Governing Law",
    "Notice",
    "Non-compete",
    "Non-solicitation",
    "Force Majeure",
    "Representations and Warranties",
]

IMPORTANCE_LEVELS = ["high", "medium", "low"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_valid_gemini_key(key: str) -> bool:
    return bool(key) and key.startswith("AIzaSy")


def _parse_json_response(raw: str) -> Optional[Dict[str, Any]]:
    """Robustly extract JSON from Gemini response."""
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown fences
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
    "You are LexGuard AI, an expert legal document clause analyzer. "
    "You extract and classify important clauses and obligations from legal documents. "
    "You return valid JSON only. Never invent clauses or obligations not present in the text. "
    "When information is missing, use exactly: \"Not specified\" or \"Not clearly stated\"."
)


def _clause_extraction_prompt(filename: str, doc_type: str,
                               jurisdiction: Optional[str], text: str) -> str:
    meta = f"Filename: {filename}\nDocument Type: {doc_type}"
    if jurisdiction:
        meta += f"\nJurisdiction: {jurisdiction}"

    clause_types_str = ", ".join(STANDARD_CLAUSE_TYPES)

    return f"""You are LexGuard AI. Analyze the legal document below and extract important clauses and obligations.

Return EXACTLY this JSON structure:
{{
  "clauses": [
    {{
      "clause_type": "Payment",
      "title": "Payment Terms",
      "description": "Client shall pay INR 5,00,000 per month within 30 days of invoice",
      "importance": "high"
    }}
  ],
  "obligations": [
    {{
      "party": "Employee",
      "obligation": "Maintain confidentiality of proprietary information",
      "deadline": "During employment and for 2 years after termination"
    }}
  ]
}}

CLAUSE TYPES TO LOOK FOR:
{clause_types_str}

IMPORTANCE LEVELS:
- high: critical terms (payment, termination, liability, indemnification)
- medium: important but not critical (notice, renewal, definitions)
- low: standard boilerplate (force majeure, miscellaneous)

STRICT RULES:
1. Return ONLY valid JSON. No markdown, no explanation outside JSON.
2. Only report clauses actually FOUND in the document. Do NOT invent.
3. If a clause type is not present, omit it from the array.
4. For obligations: identify the specific party and what they must do/not do.
5. For deadlines: extract the exact deadline if stated. If not stated, use "Not specified".
6. Keep descriptions concise (1-2 sentences max).
7. clause_type must be one of the standard types listed above.
8. importance must be exactly: "high", "medium", or "low".

DOCUMENT METADATA:
{meta}

DOCUMENT TEXT:
{text}

Return JSON now:"""


# ── Gemini analysis ───────────────────────────────────────────────────────────

def _gemini_clause_analysis(gemini: GeminiService, filename: str, doc_type: str,
                             jurisdiction: Optional[str],
                             text: str) -> Optional[Dict]:
    """Use Gemini to extract clauses and obligations."""
    raw = gemini.generate_response(
        prompt=             _clause_extraction_prompt(filename, doc_type, jurisdiction, text),
        system_instruction= _SYSTEM_PROMPT,
        temperature=        0.1,
    )
    if not raw or raw.startswith("[Google Gemini API Error"):
        return None
    return _parse_json_response(raw)


# ── Free engine fallback ──────────────────────────────────────────────────────

def _free_engine_clause_analysis(filename: str, doc_type: str,
                                  jurisdiction: Optional[str],
                                  chunks: List[Dict]) -> ClauseAnalysisResult:
    """
    Rule-based clause and obligation extraction.
    Uses regex + keyword patterns to identify standard clauses.
    """
    full_text = "\n\n".join(c["text"] for c in chunks)
    lines     = [l.strip() for l in full_text.split("\n") if l.strip()]
    lower     = full_text.lower()

    clauses     = []
    obligations = []

    # ── Clause detection patterns ─────────────────────────────────────────
    clause_patterns = [
        # Payment
        {
            "type": "Payment",
            "keywords": ["payment", "pay", "invoice", "fee", "consideration", "price"],
            "importance": "high",
            "title_template": "Payment Terms",
        },
        # Termination
        {
            "type": "Termination",
            "keywords": ["terminat", "cancel", "end this agreement", "dissolve"],
            "importance": "high",
            "title_template": "Termination Clause",
        },
        # Confidentiality
        {
            "type": "Confidentiality",
            "keywords": ["confidential", "proprietary", "non-disclosure", "nda", "secret"],
            "importance": "high",
            "title_template": "Confidentiality Obligations",
        },
        # Liability
        {
            "type": "Liability",
            "keywords": ["liability", "liable", "damages", "loss", "compensation"],
            "importance": "high",
            "title_template": "Liability Provisions",
        },
        # Indemnification
        {
            "type": "Indemnification",
            "keywords": ["indemnif", "hold harmless", "defend"],
            "importance": "high",
            "title_template": "Indemnification",
        },
        # Governing Law
        {
            "type": "Governing Law",
            "keywords": ["governing law", "governed by", "laws of"],
            "importance": "high",
            "title_template": "Governing Law",
        },
        # Dispute Resolution
        {
            "type": "Dispute Resolution",
            "keywords": ["dispute", "arbitrat", "mediati", "resolution"],
            "importance": "high",
            "title_template": "Dispute Resolution",
        },
        # Intellectual Property
        {
            "type": "Intellectual Property",
            "keywords": ["intellectual property", "copyright", "patent", "trademark", "ip rights"],
            "importance": "high",
            "title_template": "Intellectual Property",
        },
        # Term
        {
            "type": "Term",
            "keywords": ["term of", "duration", "period of", "effective date"],
            "importance": "medium",
            "title_template": "Term of Agreement",
        },
        # Renewal
        {
            "type": "Renewal",
            "keywords": ["renewal", "renew", "extend", "automatic renewal"],
            "importance": "medium",
            "title_template": "Renewal Terms",
        },
        # Notice
        {
            "type": "Notice",
            "keywords": ["notice", "notif", "written notice", "days' notice"],
            "importance": "medium",
            "title_template": "Notice Requirements",
        },
        # Definitions
        {
            "type": "Definitions",
            "keywords": ["definition", "defined", "shall mean", "interpretation"],
            "importance": "medium",
            "title_template": "Definitions",
        },
        # Representations and Warranties
        {
            "type": "Representations and Warranties",
            "keywords": ["represent", "warrant", "representation", "warranty"],
            "importance": "medium",
            "title_template": "Representations and Warranties",
        },
        # Non-compete
        {
            "type": "Non-compete",
            "keywords": ["non-compete", "non compete", "competitive", "refrain from competing"],
            "importance": "medium",
            "title_template": "Non-compete Clause",
        },
        # Non-solicitation
        {
            "type": "Non-solicitation",
            "keywords": ["non-solicit", "non solicit", "not solicit"],
            "importance": "medium",
            "title_template": "Non-solicitation",
        },
        # Force Majeure
        {
            "type": "Force Majeure",
            "keywords": ["force majeure", "act of god", "unforeseen circumstances"],
            "importance": "low",
            "title_template": "Force Majeure",
        },
        # Jurisdiction
        {
            "type": "Jurisdiction",
            "keywords": ["jurisdiction", "courts of", "exclusive jurisdiction"],
            "importance": "high",
            "title_template": "Jurisdiction",
        },
        # Privacy
        {
            "type": "Privacy",
            "keywords": ["privacy", "personal data", "data protection", "gdpr"],
            "importance": "high",
            "title_template": "Privacy and Data Protection",
        },
        # Arbitration
        {
            "type": "Arbitration",
            "keywords": ["arbitrat", "arbitral tribunal", "arbitration act"],
            "importance": "high",
            "title_template": "Arbitration",
        },
    ]

    # Find clause sources (map chunk_id and page to text snippets)
    chunk_map = {}
    for c in chunks:
        chunk_map[c["chunk_id"]] = {
            "text": c["text"],
            "page_number": c.get("page_number"),
        }

    # Detect clauses
    for pattern in clause_patterns:
        found = False
        description = ""
        source_chunk_id = None
        source_page = None

        for kw in pattern["keywords"]:
            if kw in lower:
                found = True
                # Find snippet containing keyword
                for chunk_id, chunk_data in chunk_map.items():
                    if kw in chunk_data["text"].lower():
                        # Extract sentence containing keyword
                        chunk_lines = chunk_data["text"].split("\n")
                        for line in chunk_lines:
                            if kw in line.lower() and len(line) > 20:
                                description = line.strip()[:250]
                                source_chunk_id = chunk_id
                                source_page = chunk_data["page_number"]
                                break
                        if description:
                            break
                break

        if found and description:
            clauses.append(ImportantClause(
                clause_type= pattern["type"],
                title=       pattern["title_template"],
                description= description,
                importance=  pattern["importance"],
                source=      ClauseSource(
                    page_number= source_page,
                    chunk_id=    source_chunk_id or chunks[0]["chunk_id"],
                )
            ))

    # Limit to top 15 clauses
    clauses = clauses[:15]

    # ── Obligation extraction ─────────────────────────────────────────────
    # Look for obligation keywords: shall, must, agrees to, etc.
    obligation_keywords = [
        "shall", "must", "agrees to", "required to", "obliged to",
        "shall not", "must not", "prohibited from", "may not"
    ]

    # Party extraction patterns
    party_patterns = [
        r'"([A-Z][^"]+?)"\s*\("(?:Client|Provider|Employer|Employee|Vendor|Buyer|Seller|Party\s+[AB])"\)',
        r'(?:the\s+)?(Client|Provider|Employer|Employee|Vendor|Buyer|Seller|Party\s+[AB])\s+(?:shall|must|agrees)',
    ]

    detected_parties = set()
    for pat in party_patterns:
        for m in re.finditer(pat, full_text, re.IGNORECASE):
            party = m.group(1).strip()
            if len(party) > 2 and len(party) < 50:
                detected_parties.add(party)

    if not detected_parties:
        detected_parties = {"The parties", "Each party"}

    # Extract obligations
    for chunk in chunks[:10]:  # limit search to first 10 chunks
        chunk_text = chunk["text"]
        chunk_lines = chunk_text.split("\n")

        for line in chunk_lines:
            line_clean = line.strip()
            if len(line_clean) < 30:
                continue

            # Check if line contains obligation keyword
            has_obligation = any(kw in line_clean.lower() for kw in obligation_keywords)
            if not has_obligation:
                continue

            # Try to identify party
            party = "The parties"
            for p in detected_parties:
                if p.lower() in line_clean.lower():
                    party = p
                    break

            # Extract deadline if present
            deadline_patterns = [
                r'within\s+\d+\s+(?:days?|weeks?|months?|years?)',
                r'(?:before|after|by)\s+\d+\s+(?:days?|weeks?|months?)',
                r'for\s+a\s+period\s+of\s+\d+\s+(?:days?|weeks?|months?|years?)',
                r'during\s+(?:employment|the\s+term)',
                r'upon\s+(?:termination|expiry|completion)',
            ]
            deadline = "Not specified"
            for pat in deadline_patterns:
                m = re.search(pat, line_clean, re.IGNORECASE)
                if m:
                    deadline = m.group().strip()
                    break

            obligations.append(Obligation(
                party=      party,
                obligation= line_clean[:300],
                deadline=   deadline,
                source=     ClauseSource(
                    page_number= chunk.get("page_number"),
                    chunk_id=    chunk["chunk_id"],
                )
            ))

            if len(obligations) >= 12:
                break

        if len(obligations) >= 12:
            break

    if not obligations:
        obligations.append(Obligation(
            party=      "Not identified",
            obligation= "Obligations not clearly parsed — review document manually.",
            deadline=   "Not specified",
            source=     ClauseSource(
                page_number= chunks[0].get("page_number") if chunks else None,
                chunk_id=    chunks[0]["chunk_id"] if chunks else "unknown",
            )
        ))

    return ClauseAnalysisResult(
        clauses=            clauses,
        obligations=        obligations[:12],
        provider_used=      "LexGuard Free Clause Engine",
        analysis_successful=True,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_clauses_and_obligations(
    filename:    str,
    doc_type:    str,
    jurisdiction: Optional[str],
    chunks:      List[Dict],  # [{"text": str, "chunk_id": str, "page_number": int|None}]
) -> ClauseAnalysisResult:
    """
    Extract important clauses and obligations from document chunks.

    Parameters
    ----------
    filename     : original document filename
    doc_type     : DocumentType.value string
    jurisdiction : optional jurisdiction
    chunks       : list of dicts with keys: text, chunk_id, page_number

    Returns
    -------
    ClauseAnalysisResult with clauses and obligations arrays
    """
    if not chunks:
        return ClauseAnalysisResult(
            clauses=            [],
            obligations=        [],
            analysis_successful=False,
            error_message=      "No text chunks available for clause analysis",
        )

    full_text = "\n\n".join(c["text"] for c in chunks)[:MAX_TEXT_FOR_CLAUSE_ANALYSIS]

    # ── Try Gemini ─────────────────────────────────────────────────────────
    api_key = get_gemini_api_key()
    if _is_valid_gemini_key(api_key):
        try:
            gemini = GeminiService(api_key=api_key)
            parsed = _gemini_clause_analysis(gemini, filename, doc_type,
                                              jurisdiction, full_text)
            if parsed:
                # Build structured results from Gemini response
                clause_objs = []
                for c_dict in parsed.get("clauses", []):
                    # Find best matching chunk for source
                    clause_text = c_dict.get("description", "").lower()
                    best_chunk = chunks[0]  # default
                    for chunk in chunks:
                        if any(word in chunk["text"].lower() for word in clause_text.split()[:5]):
                            best_chunk = chunk
                            break

                    clause_objs.append(ImportantClause(
                        clause_type= c_dict.get("clause_type", "Unknown"),
                        title=       c_dict.get("title", "Untitled"),
                        description= c_dict.get("description", ""),
                        importance=  c_dict.get("importance", "medium")
                                     if c_dict.get("importance") in IMPORTANCE_LEVELS
                                     else "medium",
                        source=      ClauseSource(
                            page_number= best_chunk.get("page_number"),
                            chunk_id=    best_chunk.get("chunk_id", "unknown"),
                        )
                    ))

                obligation_objs = []
                for o_dict in parsed.get("obligations", []):
                    obl_text = o_dict.get("obligation", "").lower()
                    best_chunk = chunks[0]
                    for chunk in chunks:
                        if any(word in chunk["text"].lower() for word in obl_text.split()[:5]):
                            best_chunk = chunk
                            break

                    obligation_objs.append(Obligation(
                        party=      o_dict.get("party", "Not identified"),
                        obligation= o_dict.get("obligation", ""),
                        deadline=   o_dict.get("deadline", "Not specified"),
                        source=     ClauseSource(
                            page_number= best_chunk.get("page_number"),
                            chunk_id=    best_chunk.get("chunk_id", "unknown"),
                        )
                    ))

                return ClauseAnalysisResult(
                    clauses=            clause_objs[:15],
                    obligations=        obligation_objs[:12],
                    provider_used=      "Google Gemini AI",
                    analysis_successful=True,
                )

        except Exception as exc:
            logger.warning("Gemini clause analysis failed: %s", exc)

    # ── Fallback — rule-based engine ───────────────────────────────────────
    return _free_engine_clause_analysis(filename, doc_type, jurisdiction, chunks)
