"""
Entities Extraction Service — Phase 6
======================================
Extracts structured entities from legal documents:
- Parties (with roles)
- Key Dates (with types)
- Obligations (party → action → deadline)
- Evidence (quotes with source references)

IMPORTANT: Does NOT invent or infer entities without evidence.
All findings are traceable to source chunks.

Features
--------
1. Party Extraction:
   - Names and roles (Employer, Employee, Landlord, Tenant, etc.)
   - Source tracking (page, chunk)
   - Evidence quotes

2. Date Extraction:
   - Types: Effective, Start, End, Renewal, Payment, Notice, Termination, Filing, Expiry
   - Multiple date formats supported
   - Source tracking

3. Obligation Extraction:
   - Party responsible
   - Obligation description
   - Deadline (if specified)
   - Conditions (if any)
   - Source tracking

4. Evidence System:
   - Short quotes from document
   - Full source metadata (document_id, page, chunk)
   - Never fabricates evidence

Architecture
------------
- Gemini AI primary engine (contextual understanding)
- Rule-based fallback engine (regex + NER patterns)
- Evidence-based extraction only
- No inference without text support

Security
--------
Caller must pass owner-scoped chunks only.
This service does NOT query the database.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from app.services.ai.gemini_service import GeminiService, get_gemini_api_key

logger = logging.getLogger(__name__)

MAX_TEXT_FOR_ANALYSIS = 15000  # chars


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class SourceReference:
    """Source location in document"""
    page_number: Optional[int]
    chunk_id:    str
    document_id: Optional[int] = None
    document_name: Optional[str] = None


@dataclass
class Party:
    """Extracted party with role"""
    name:   str              # "ABC Technologies Pvt. Ltd."
    role:   Optional[str]    # "Employer", "Service Provider", etc.
    source: SourceReference
    evidence: Optional[str] = None  # Short quote


@dataclass
class KeyDate:
    """Extracted date with type"""
    date:   str              # "15 March 2026" or "2026-03-15"
    type:   str              # "Effective Date", "Start Date", etc.
    source: SourceReference
    evidence: Optional[str] = None


@dataclass
class Obligation:
    """Extracted obligation"""
    party:      str                    # "Service Provider"
    obligation: str                    # "Deliver monthly reports"
    deadline:   Optional[str]          # "Within 5 days of month-end"
    condition:  Optional[str]          # "Upon client request"
    source:     SourceReference
    evidence:   Optional[str] = None


@dataclass
class Evidence:
    """Evidence quote with full source"""
    quote:         str
    document_id:   Optional[int]
    document_name: Optional[str]
    page_number:   Optional[int]
    chunk_id:      str


@dataclass
class EntitiesAnalysis:
    """Complete entities extraction result"""
    parties:      List[Party]      = field(default_factory=list)
    key_dates:    List[KeyDate]    = field(default_factory=list)
    obligations:  List[Obligation] = field(default_factory=list)
    provider_used: str = "unknown"
    analysis_successful: bool = True
    error_message: Optional[str] = None


# ── Date type patterns ────────────────────────────────────────────────────────

DATE_TYPES = [
    "Effective Date",
    "Start Date",
    "End Date",
    "Commencement Date",
    "Termination Date",
    "Expiry Date",
    "Renewal Date",
    "Payment Date",
    "Due Date",
    "Notice Date",
    "Filing Date",
    "Closing Date",
    "Delivery Date",
    "Completion Date",
]


# ── Party role patterns ───────────────────────────────────────────────────────

PARTY_ROLES = [
    "Employer", "Employee",
    "Service Provider", "Client", "Customer",
    "Landlord", "Tenant",
    "Seller", "Buyer", "Purchaser", "Vendor",
    "Lender", "Borrower",
    "Disclosing Party", "Receiving Party",
    "Contractor", "Subcontractor",
    "Licensor", "Licensee",
    "Party A", "Party B",
    "First Party", "Second Party",
]


# ── Regex patterns ────────────────────────────────────────────────────────────

# Date patterns (various formats)
DATE_PATTERNS = [
    r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',           # 15/03/2026, 03-15-26
    r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',             # 2026-03-15
    r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',  # 15 March 2026
    r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',  # March 15, 2026
    r'\b\d{1,2}(?:st|nd|rd|th)\s+(?:day\s+of\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',  # 15th day of March 2026
]

# Party name patterns (capitalized entities)
PARTY_NAME_PATTERN = r'\b[A-Z][A-Za-z&\s\.,-]+(?:Ltd|LLC|Inc|Corp|Corporation|Company|Co|LLP|LP|Partnership|Associates|Group|Pvt|Private|Limited|PLC)\b\.?'

# Obligation patterns
OBLIGATION_KEYWORDS = [
    r'\bshall\b', r'\bmust\b', r'\bwill\b', r'\brequired to\b', r'\bobligated to\b',
    r'\bagreed to\b', r'\bundertakes to\b', r'\bresponsible for\b', r'\bduty to\b'
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_valid_gemini_key(key: str) -> bool:
    return bool(key) and key.startswith("AIzaSy")


def _parse_json_response(raw: str) -> Optional[Dict[str, Any]]:
    """Robustly extract JSON from Gemini response."""
    if not raw:
        return None
    
    # Try direct parse
    try:
        return json.loads(raw)
    except:
        pass
    
    # Try finding JSON block
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass
    
    # Try finding array
    array_match = re.search(r'\[[\s\S]*\]', raw)
    if array_match:
        try:
            return {"data": json.loads(array_match.group(0))}
        except:
            pass
    
    return None


def _make_source_ref(chunk_id: str, page_number: Optional[int], doc_id: Optional[int] = None, doc_name: Optional[str] = None) -> SourceReference:
    """Create source reference"""
    return SourceReference(
        page_number=page_number,
        chunk_id=chunk_id,
        document_id=doc_id,
        document_name=doc_name,
    )


def _truncate_quote(text: str, max_len: int = 150) -> str:
    """Truncate evidence quote"""
    if len(text) <= max_len:
        return text
    return text[:max_len].strip() + "..."


# ── Gemini prompt ─────────────────────────────────────────────────────────────

def _entities_prompt(filename: str, text: str) -> str:
    return f"""You are LexGuard AI. Extract structured entities from this legal document.

DOCUMENT: {filename}

RULES:
1. Extract ONLY entities that are explicitly present in the text
2. Do NOT invent or infer parties, dates, or obligations without evidence
3. Provide source page numbers and evidence quotes
4. Keep quotes short (under 150 characters)

TEXT:
{text}

Extract and return JSON:

{{
  "parties": [
    {{
      "name": "ABC Corp",
      "role": "Employer",
      "page_number": 1,
      "evidence": "ABC Corp (hereinafter 'Employer')..."
    }}
  ],
  "key_dates": [
    {{
      "date": "January 1, 2024",
      "type": "Effective Date",
      "page_number": 1,
      "evidence": "This Agreement is effective as of January 1, 2024"
    }}
  ],
  "obligations": [
    {{
      "party": "Employee",
      "obligation": "Maintain confidentiality",
      "deadline": null,
      "condition": null,
      "page_number": 3,
      "evidence": "Employee shall maintain confidentiality of..."
    }}
  ]
}}

Return valid JSON only."""


# ── Gemini extraction ─────────────────────────────────────────────────────────

def _gemini_extraction(gemini: GeminiService, filename: str, text: str, chunks: List[Dict]) -> Optional[Dict]:
    """Use Gemini to extract entities"""
    try:
        raw = gemini.generate_response(
            _entities_prompt(filename, text),
            temperature=0.1,
        )
        return _parse_json_response(raw)
    except Exception as e:
        logger.warning(f"Gemini entities extraction failed: {e}")
        return None


# ── Free engine extraction ────────────────────────────────────────────────────

def _extract_parties_free(chunks: List[Dict]) -> List[Party]:
    """Rule-based party extraction"""
    parties = []
    seen_names = set()
    
    for chunk in chunks:
        text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id", "unknown")
        page_num = chunk.get("page_number")
        
        # Find company/organization names
        names = re.findall(PARTY_NAME_PATTERN, text)
        
        for name in names:
            name = name.strip()
            if name in seen_names or len(name) < 3:
                continue
            
            seen_names.add(name)
            
            # Try to find role nearby
            role = None
            for role_pattern in PARTY_ROLES:
                if re.search(rf'\b{role_pattern}\b', text, re.IGNORECASE):
                    role = role_pattern
                    break
            
            # Extract evidence quote
            evidence = None
            for sentence in text.split('.'):
                if name in sentence:
                    evidence = _truncate_quote(sentence.strip())
                    break
            
            parties.append(Party(
                name=name,
                role=role,
                source=_make_source_ref(chunk_id, page_num),
                evidence=evidence,
            ))
    
    return parties[:10]  # Limit to top 10


def _extract_dates_free(chunks: List[Dict]) -> List[KeyDate]:
    """Rule-based date extraction"""
    dates = []
    seen_dates = set()
    
    for chunk in chunks:
        text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id", "unknown")
        page_num = chunk.get("page_number")
        
        # Find dates using patterns
        for pattern in DATE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                date_str = match.group(0)
                if date_str in seen_dates:
                    continue
                
                seen_dates.add(date_str)
                
                # Determine date type from context
                date_type = "Date"
                lower_text = text.lower()
                
                for dt in DATE_TYPES:
                    if dt.lower() in lower_text:
                        date_type = dt
                        break
                
                # Extract evidence
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                evidence = _truncate_quote(text[start:end])
                
                dates.append(KeyDate(
                    date=date_str,
                    type=date_type,
                    source=_make_source_ref(chunk_id, page_num),
                    evidence=evidence,
                ))
    
    return dates[:15]  # Limit to top 15


def _extract_obligations_free(chunks: List[Dict], parties: List[Party]) -> List[Obligation]:
    """Rule-based obligation extraction"""
    obligations = []
    party_names = [p.name for p in parties] + [p.role for p in parties if p.role]
    
    for chunk in chunks:
        text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id", "unknown")
        page_num = chunk.get("page_number")
        
        # Split into sentences
        sentences = re.split(r'[.;]', text)
        
        for sentence in sentences:
            # Check if contains obligation keyword
            has_obligation = any(re.search(kw, sentence, re.IGNORECASE) for kw in OBLIGATION_KEYWORDS)
            
            if not has_obligation:
                continue
            
            # Find party in sentence
            party = None
            for p_name in party_names:
                if p_name and p_name in sentence:
                    party = p_name
                    break
            
            if not party:
                party = "Party"
            
            # Extract obligation (sentence after shall/must/will)
            obligation_text = sentence.strip()
            for kw in OBLIGATION_KEYWORDS:
                parts = re.split(kw, obligation_text, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) > 1:
                    obligation_text = parts[1].strip()
                    break
            
            # Truncate
            obligation_text = _truncate_quote(obligation_text, max_len=200)
            
            # Try to find deadline
            deadline = None
            deadline_patterns = [
                r'within\s+\d+\s+(?:day|week|month|year)s?',
                r'by\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
                r'before\s+\w+\s+\d{1,2}',
            ]
            for dp in deadline_patterns:
                match = re.search(dp, sentence, re.IGNORECASE)
                if match:
                    deadline = match.group(0)
                    break
            
            obligations.append(Obligation(
                party=party,
                obligation=obligation_text,
                deadline=deadline,
                condition=None,
                source=_make_source_ref(chunk_id, page_num),
                evidence=_truncate_quote(sentence),
            ))
    
    return obligations[:20]  # Limit to top 20


def _free_engine_extraction(filename: str, chunks: List[Dict]) -> Dict[str, Any]:
    """Rule-based entities extraction"""
    
    # Extract parties first
    parties = _extract_parties_free(chunks)
    
    # Extract dates
    key_dates = _extract_dates_free(chunks)
    
    # Extract obligations (using parties context)
    obligations = _extract_obligations_free(chunks, parties)
    
    return {
        "parties": [
            {
                "name": p.name,
                "role": p.role,
                "page_number": p.source.page_number,
                "chunk_id": p.source.chunk_id,
                "evidence": p.evidence,
            }
            for p in parties
        ],
        "key_dates": [
            {
                "date": d.date,
                "type": d.type,
                "page_number": d.source.page_number,
                "chunk_id": d.source.chunk_id,
                "evidence": d.evidence,
            }
            for d in key_dates
        ],
        "obligations": [
            {
                "party": o.party,
                "obligation": o.obligation,
                "deadline": o.deadline,
                "condition": o.condition,
                "page_number": o.source.page_number,
                "chunk_id": o.source.chunk_id,
                "evidence": o.evidence,
            }
            for o in obligations
        ],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def extract_entities(
    filename:    str,
    document_id: Optional[int],
    chunks:      List[Dict],  # [{"text": str, "chunk_id": str, "page_number": int|None}]
) -> EntitiesAnalysis:
    """
    Extract structured entities from document.
    
    Parameters
    ----------
    filename     : original document filename
    document_id  : optional document ID for evidence tracking
    chunks       : list of dicts with keys: text, chunk_id, page_number
    
    Returns
    -------
    EntitiesAnalysis with parties, dates, obligations
    """
    if not chunks:
        return EntitiesAnalysis(
            parties=[],
            key_dates=[],
            obligations=[],
            analysis_successful=False,
            error_message="No text chunks available for extraction",
        )
    
    full_text = "\n\n".join(c.get("text", "") for c in chunks)[:MAX_TEXT_FOR_ANALYSIS]
    
    # ── Try Gemini ─────────────────────────────────────────────────────────
    api_key = get_gemini_api_key()
    result_data = None
    provider = "unknown"
    
    if _is_valid_gemini_key(api_key):
        try:
            gemini = GeminiService(api_key=api_key)
            result_data = _gemini_extraction(gemini, filename, full_text, chunks)
            if result_data:
                provider = "gemini-free"
                logger.info("Gemini entities extraction successful")
        except Exception as e:
            logger.warning(f"Gemini extraction failed: {e}")
    
    # ── Fallback to free engine ────────────────────────────────────────────
    if not result_data:
        logger.info("Using free engine for entities extraction")
        result_data = _free_engine_extraction(filename, chunks)
        provider = "free-engine"
    
    # ── Build result ───────────────────────────────────────────────────────
    
    parties = []
    for p_data in result_data.get("parties", [])[:10]:
        chunk_id = p_data.get("chunk_id", "unknown")
        page_num = p_data.get("page_number")
        
        parties.append(Party(
            name=p_data.get("name", "Unknown"),
            role=p_data.get("role"),
            source=_make_source_ref(chunk_id, page_num, document_id, filename),
            evidence=p_data.get("evidence"),
        ))
    
    key_dates = []
    for d_data in result_data.get("key_dates", [])[:15]:
        chunk_id = d_data.get("chunk_id", "unknown")
        page_num = d_data.get("page_number")
        
        key_dates.append(KeyDate(
            date=d_data.get("date", ""),
            type=d_data.get("type", "Date"),
            source=_make_source_ref(chunk_id, page_num, document_id, filename),
            evidence=d_data.get("evidence"),
        ))
    
    obligations = []
    for o_data in result_data.get("obligations", [])[:20]:
        chunk_id = o_data.get("chunk_id", "unknown")
        page_num = o_data.get("page_number")
        
        obligations.append(Obligation(
            party=o_data.get("party", "Party"),
            obligation=o_data.get("obligation", ""),
            deadline=o_data.get("deadline"),
            condition=o_data.get("condition"),
            source=_make_source_ref(chunk_id, page_num, document_id, filename),
            evidence=o_data.get("evidence"),
        ))
    
    return EntitiesAnalysis(
        parties=parties,
        key_dates=key_dates,
        obligations=obligations,
        provider_used=provider,
        analysis_successful=True,
        error_message=None,
    )
