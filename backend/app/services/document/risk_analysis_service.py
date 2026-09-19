"""
Risk Analysis Service — Phase 4
================================
Identifies legal risks in documents with severity classification and confidence scoring.

IMPORTANT: This provides AI-assisted legal information, NOT definitive legal advice.

Features
--------
1. Risk Detection:
   - 12 standard risk categories
   - Evidence-based identification
   - Confidence scoring (0.0-1.0)
   
2. Risk Categories:
   - Financial Risk
   - Termination Risk
   - Liability Risk
   - Confidentiality Risk
   - Privacy Risk
   - Intellectual Property Risk
   - Compliance Risk
   - Dispute Resolution Risk
   - Jurisdiction Risk
   - Ambiguity Risk
   - Missing Clause Risk
   - Unfavorable Obligation Risk

3. Severity Levels:
   - high: Critical risks requiring immediate attention
   - medium: Important risks warranting review
   - low: Minor risks or standard provisions

4. Overall Risk Assessment:
   - Low: Generally favorable terms
   - Moderate: Some concerns present
   - High: Multiple significant risks identified

Architecture
------------
- Gemini AI primary engine (contextual risk analysis)
- Rule-based fallback engine (pattern matching + heuristics)
- Evidence requirement: every risk must cite document text
- Confidence scoring based on evidence strength

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

MAX_TEXT_FOR_RISK_ANALYSIS = 15000  # chars


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class RiskSource:
    page_number: Optional[int]
    chunk_id:    str


@dataclass
class IdentifiedRisk:
    category:    str           # "Financial Risk", "Termination Risk", etc.
    severity:    str           # "high", "medium", "low"
    title:       str           # brief description
    description: str           # detailed explanation
    reason:      str           # why this is risky
    evidence:    str           # supporting document text
    confidence:  float         # 0.0 - 1.0
    source:      RiskSource


@dataclass
class RiskAssessment:
    overall_risk:    str                          # "Low", "Moderate", "High"
    risk_score:      float                        # 0.0 - 10.0
    factors:         List[str]                    # contributing factors
    risks:           List[IdentifiedRisk] = field(default_factory=list)
    provider_used:   str = "LexGuard Free Risk Engine"
    analysis_successful: bool = True
    error_message:   Optional[str] = None


# ── Standard risk categories ──────────────────────────────────────────────────

RISK_CATEGORIES = [
    "Financial Risk",
    "Termination Risk",
    "Liability Risk",
    "Confidentiality Risk",
    "Privacy Risk",
    "Intellectual Property Risk",
    "Compliance Risk",
    "Dispute Resolution Risk",
    "Jurisdiction Risk",
    "Ambiguity Risk",
    "Missing Clause Risk",
    "Unfavorable Obligation Risk",
]

SEVERITY_LEVELS = ["high", "medium", "low"]
OVERALL_RISK_LEVELS = ["Low", "Moderate", "High"]


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


def _calculate_overall_risk(risks: List[IdentifiedRisk]) -> tuple[str, float, List[str]]:
    """
    Calculate overall risk level from individual risks.
    
    Returns (risk_level, risk_score, factors)
    - risk_level: "Low", "Moderate", "High"
    - risk_score: 0.0 - 10.0
    - factors: List of contributing factors
    """
    if not risks:
        return "Low", 0.0, ["No significant risks identified in document"]
    
    # Count risks by severity
    high_count   = sum(1 for r in risks if r.severity == "high")
    medium_count = sum(1 for r in risks if r.severity == "medium")
    low_count    = sum(1 for r in risks if r.severity == "low")
    
    # Weight risks
    weighted_score = (high_count * 3.0) + (medium_count * 1.5) + (low_count * 0.5)
    
    # Normalize to 0-10 scale (cap at 10)
    risk_score = min(10.0, weighted_score)
    
    # Determine overall level
    if risk_score >= 7.0 or high_count >= 3:
        overall = "High"
    elif risk_score >= 3.5 or high_count >= 1:
        overall = "Moderate"
    else:
        overall = "Low"
    
    # Build factors list
    factors = []
    if high_count > 0:
        factors.append(f"{high_count} high-severity risk{'s' if high_count > 1 else ''} identified")
    if medium_count > 0:
        factors.append(f"{medium_count} medium-severity risk{'s' if medium_count > 1 else ''} present")
    if low_count > 0:
        factors.append(f"{low_count} low-severity risk{'s' if low_count > 1 else ''} noted")
    
    # Add qualitative factors
    categories = {r.category for r in risks}
    if "Financial Risk" in categories or "Liability Risk" in categories:
        factors.append("Financial or liability concerns present")
    if "Termination Risk" in categories:
        factors.append("Termination provisions may be unfavorable")
    if "Missing Clause Risk" in categories or "Ambiguity Risk" in categories:
        factors.append("Missing or ambiguous protections identified")
    
    return overall, risk_score, factors[:5]  # limit to 5 factors


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are LexGuard AI, an expert legal risk analyst. "
    "You identify potential legal risks in documents with supporting evidence. "
    "You provide AI-assisted legal information, NOT definitive legal advice. "
    "You return valid JSON only. Every risk MUST have supporting evidence from the document. "
    "Never invent risks without document evidence. Be balanced—not everything is high risk."
)


def _risk_analysis_prompt(filename: str, doc_type: str,
                          jurisdiction: Optional[str], text: str) -> str:
    meta = f"Filename: {filename}\nDocument Type: {doc_type}"
    if jurisdiction:
        meta += f"\nJurisdiction: {jurisdiction}"

    categories_str = ", ".join(RISK_CATEGORIES)

    return f"""You are LexGuard AI. Analyze the legal document below for potential risks.

Return EXACTLY this JSON structure:
{{
  "risks": [
    {{
      "category": "Termination Risk",
      "severity": "high",
      "title": "Broad termination provision",
      "description": "Employer can terminate without cause with minimal notice",
      "reason": "Provides limited job security; employee can be dismissed easily",
      "evidence": "Exact quote from document showing the risky provision",
      "confidence": 0.87
    }}
  ]
}}

RISK CATEGORIES:
{categories_str}

SEVERITY GUIDELINES:
- high: Critical risks requiring immediate attention (broad liability, unfavorable termination, missing protections)
- medium: Important risks warranting review (ambiguous terms, moderate concerns)
- low: Minor risks or standard provisions (common boilerplate, typical clauses)

CRITICAL RULES:
1. Return ONLY valid JSON. No markdown, no explanation outside JSON.
2. Every risk MUST have supporting evidence (exact quote from document).
3. If no evidence exists, DO NOT report the risk.
4. Confidence score: 0.0 (uncertain) to 1.0 (highly confident).
5. Do NOT mark everything as high severity. Be balanced and realistic.
6. Focus on actual document language, not hypothetical concerns.
7. Category must be one of the standard types listed above.
8. Severity must be exactly: "high", "medium", or "low".
9. Consider context: employment vs service vs sale contract.

DOCUMENT METADATA:
{meta}

DOCUMENT TEXT:
{text}

Return JSON now:"""


# ── Gemini analysis ───────────────────────────────────────────────────────────

def _gemini_risk_analysis(gemini: GeminiService, filename: str, doc_type: str,
                          jurisdiction: Optional[str], text: str) -> Optional[Dict]:
    """Use Gemini to identify legal risks."""
    raw = gemini.generate_response(
        prompt=             _risk_analysis_prompt(filename, doc_type, jurisdiction, text),
        system_instruction= _SYSTEM_PROMPT,
        temperature=        0.2,  # slightly higher for nuanced risk assessment
    )
    if not raw or raw.startswith("[Google Gemini API Error"):
        return None
    return _parse_json_response(raw)


# ── Free engine fallback ──────────────────────────────────────────────────────

def _free_engine_risk_analysis(filename: str, doc_type: str,
                                jurisdiction: Optional[str],
                                chunks: List[Dict]) -> RiskAssessment:
    """
    Rule-based risk detection.
    Uses pattern matching and heuristics to identify common legal risks.
    """
    full_text = "\n\n".join(c["text"] for c in chunks)
    lower = full_text.lower()
    risks = []
    
    # Chunk map for source references
    chunk_map = {}
    for c in chunks:
        chunk_map[c["chunk_id"]] = {
            "text": c["text"],
            "page_number": c.get("page_number"),
        }
    
    # ── Risk Detection Patterns ───────────────────────────────────────────
    
    # 1. TERMINATION RISK
    termination_patterns = [
        (r"terminate\s+(?:at\s+)?(?:any\s+time|immediately|without\s+(?:cause|reason|notice))", 
         "Broad termination rights", 0.85),
        (r"(?:may|can)\s+terminate\s+(?:this\s+agreement\s+)?(?:with|by\s+giving)\s+(?:\d+\s+)?(?:days?|hours?)\s+notice",
         "Minimal notice period", 0.75),
        (r"employer\s+(?:may|can|reserves?\s+the\s+right\s+to)\s+terminate",
         "Employer termination discretion", 0.70),
    ]
    
    for pattern, title, conf in termination_patterns:
        matches = list(re.finditer(pattern, lower, re.IGNORECASE))
        if matches:
            # Find source
            evidence = matches[0].group()
            source_chunk = chunks[0]
            for chunk in chunks:
                if evidence[:30].lower() in chunk["text"].lower():
                    source_chunk = chunk
                    break
            
            # Extract fuller evidence
            for line in full_text.split('\n'):
                if evidence[:20].lower() in line.lower():
                    evidence = line.strip()[:200]
                    break
            
            risks.append(IdentifiedRisk(
                category=    "Termination Risk",
                severity=    "high" if "without" in evidence.lower() or "at any time" in evidence.lower() else "medium",
                title=       title,
                description= f"The document allows termination {evidence[:50]}...",
                reason=      "Provides limited protection against unexpected termination",
                evidence=    evidence,
                confidence=  conf,
                source=      RiskSource(
                    page_number= source_chunk.get("page_number"),
                    chunk_id=    source_chunk["chunk_id"],
                )
            ))
            break  # only report once per category
    
    # 2. LIABILITY RISK
    liability_patterns = [
        (r"unlimited\s+liability", "Unlimited liability exposure", 0.90),
        (r"liable\s+for\s+(?:all|any)\s+(?:damages|losses|claims)", "Broad liability", 0.80),
        (r"indemnify.*(?:against\s+all|for\s+any)", "Broad indemnification", 0.75),
        (r"no\s+(?:limit|cap)\s+(?:on|to)\s+liability", "No liability cap", 0.85),
    ]
    
    for pattern, title, conf in liability_patterns:
        matches = list(re.finditer(pattern, lower, re.IGNORECASE))
        if matches:
            evidence = matches[0].group()
            source_chunk = chunks[0]
            for chunk in chunks:
                if evidence[:30].lower() in chunk["text"].lower():
                    source_chunk = chunk
                    break
            
            for line in full_text.split('\n'):
                if evidence[:20].lower() in line.lower():
                    evidence = line.strip()[:200]
                    break
            
            risks.append(IdentifiedRisk(
                category=    "Liability Risk",
                severity=    "high" if "unlimited" in evidence.lower() or "no limit" in evidence.lower() else "medium",
                title=       title,
                description= f"Liability provisions state: {evidence[:60]}...",
                reason=      "May expose party to significant financial risk",
                evidence=    evidence,
                confidence=  conf,
                source=      RiskSource(
                    page_number= source_chunk.get("page_number"),
                    chunk_id=    source_chunk["chunk_id"],
                )
            ))
            break
    
    # 3. FINANCIAL RISK
    financial_patterns = [
        (r"late\s+(?:payment\s+)?(?:fee|penalty|charge).*?(\d+)\s*%", "High late payment penalty", 0.80),
        (r"non-refundable", "Non-refundable payments", 0.70),
        (r"payment\s+in\s+advance", "Advance payment required", 0.60),
        (r"penalty\s+of.*?(?:INR|USD|EUR|\$|₹)\s*[\d,]+", "Financial penalties", 0.75),
    ]
    
    for pattern, title, conf in financial_patterns:
        matches = list(re.finditer(pattern, lower, re.IGNORECASE))
        if matches:
            evidence = matches[0].group()
            source_chunk = chunks[0]
            for chunk in chunks:
                if evidence[:30].lower() in chunk["text"].lower():
                    source_chunk = chunk
                    break
            
            for line in full_text.split('\n'):
                if evidence[:20].lower() in line.lower():
                    evidence = line.strip()[:200]
                    break
            
            severity = "high" if "%" in evidence and any(str(i) in evidence for i in range(5, 20)) else "medium"
            
            risks.append(IdentifiedRisk(
                category=    "Financial Risk",
                severity=    severity,
                title=       title,
                description= f"Financial terms include: {evidence[:60]}...",
                reason=      "May result in unexpected financial burden",
                evidence=    evidence,
                confidence=  conf,
                source=      RiskSource(
                    page_number= source_chunk.get("page_number"),
                    chunk_id=    source_chunk["chunk_id"],
                )
            ))
            break
    
    # 4. CONFIDENTIALITY RISK
    if re.search(r"confidential(?:ity)?", lower):
        conf_patterns = [
            (r"indefinite(?:ly)?.*?confidential", "Indefinite confidentiality", 0.75),
            (r"confidential.*?(?:perpetuity|forever|permanently)", "Perpetual confidentiality", 0.80),
            (r"breach.*?confidential.*?(?:injunction|specific\s+performance)", "Injunctive relief for breach", 0.70),
        ]
        
        for pattern, title, conf in conf_patterns:
            matches = list(re.finditer(pattern, lower, re.IGNORECASE))
            if matches:
                evidence = matches[0].group()
                source_chunk = chunks[0]
                for chunk in chunks:
                    if evidence[:30].lower() in chunk["text"].lower():
                        source_chunk = chunk
                        break
                
                for line in full_text.split('\n'):
                    if evidence[:20].lower() in line.lower():
                        evidence = line.strip()[:200]
                        break
                
                risks.append(IdentifiedRisk(
                    category=    "Confidentiality Risk",
                    severity=    "medium",
                    title=       title,
                    description= f"Confidentiality clause states: {evidence[:60]}...",
                    reason=      "Imposes long-term or strict confidentiality obligations",
                    evidence=    evidence,
                    confidence=  conf,
                    source=      RiskSource(
                        page_number= source_chunk.get("page_number"),
                        chunk_id=    source_chunk["chunk_id"],
                    )
                ))
                break
    
    # 5. INTELLECTUAL PROPERTY RISK
    ip_patterns = [
        (r"all\s+(?:rights|ip|intellectual\s+property).*?(?:belong|vest|assign).*?(?:to|in)",
         "IP rights assignment", 0.80),
        (r"work\s+for\s+hire", "Work for hire arrangement", 0.85),
        (r"waive.*?moral\s+rights", "Moral rights waiver", 0.75),
    ]
    
    for pattern, title, conf in ip_patterns:
        matches = list(re.finditer(pattern, lower, re.IGNORECASE))
        if matches:
            evidence = matches[0].group()
            source_chunk = chunks[0]
            for chunk in chunks:
                if evidence[:30].lower() in chunk["text"].lower():
                    source_chunk = chunk
                    break
            
            for line in full_text.split('\n'):
                if evidence[:20].lower() in line.lower():
                    evidence = line.strip()[:200]
                    break
            
            risks.append(IdentifiedRisk(
                category=    "Intellectual Property Risk",
                severity=    "medium",
                title=       title,
                description= f"IP provisions state: {evidence[:60]}...",
                reason=      "May result in loss of IP rights or ownership",
                evidence=    evidence,
                confidence=  conf,
                source=      RiskSource(
                    page_number= source_chunk.get("page_number"),
                    chunk_id=    source_chunk["chunk_id"],
                )
            ))
            break
    
    # 6. JURISDICTION RISK
    if jurisdiction and re.search(r"jurisdiction|governing\s+law", lower):
        # Check if jurisdiction matches
        if jurisdiction.lower() not in lower:
            # Find the actual jurisdiction mentioned
            jur_match = re.search(r"(?:laws?\s+of|courts?\s+(?:of|in)|jurisdiction\s+of)\s+([A-Za-z\s]+?)(?:\.|,|;|\sand\s)", lower)
            if jur_match:
                found_jur = jur_match.group(1).strip()
                if found_jur.lower() != jurisdiction.lower():
                    risks.append(IdentifiedRisk(
                        category=    "Jurisdiction Risk",
                        severity=    "medium",
                        title=       "Different jurisdiction specified",
                        description= f"Document specifies {found_jur} jurisdiction",
                        reason=      f"May require legal proceedings in {found_jur} rather than {jurisdiction}",
                        evidence=    jur_match.group()[:200],
                        confidence=  0.80,
                        source=      RiskSource(
                            page_number= chunks[0].get("page_number"),
                            chunk_id=    chunks[0]["chunk_id"],
                        )
                    ))
    
    # 7. AMBIGUITY RISK
    ambiguity_keywords = [
        "reasonable", "appropriate", "adequate", "sufficient", 
        "as soon as practicable", "best efforts", "commercially reasonable"
    ]
    ambiguous_count = sum(1 for kw in ambiguity_keywords if kw in lower)
    
    if ambiguous_count >= 3:
        # Find an example
        for kw in ambiguity_keywords:
            if kw in lower:
                idx = lower.index(kw)
                evidence = full_text[max(0, idx-50):idx+100].strip()
                
                source_chunk = chunks[0]
                for chunk in chunks:
                    if kw in chunk["text"].lower():
                        source_chunk = chunk
                        break
                
                risks.append(IdentifiedRisk(
                    category=    "Ambiguity Risk",
                    severity=    "low" if ambiguous_count < 5 else "medium",
                    title=       "Multiple ambiguous terms",
                    description= f"Document contains {ambiguous_count} ambiguous terms like '{kw}'",
                    reason=      "Vague language may lead to interpretation disputes",
                    evidence=    evidence[:200],
                    confidence=  0.70,
                    source=      RiskSource(
                        page_number= source_chunk.get("page_number"),
                        chunk_id=    source_chunk["chunk_id"],
                    )
                ))
                break
    
    # 8. MISSING CLAUSE RISK
    standard_clauses = {
        "force majeure": "Force majeure clause",
        "limitation of liability": "Liability limitation",
        "dispute resolution": "Dispute resolution mechanism",
        "termination": "Termination provisions",
    }
    
    missing = []
    for keyword, clause_name in standard_clauses.items():
        if keyword not in lower:
            missing.append(clause_name)
    
    if len(missing) >= 2:
        risks.append(IdentifiedRisk(
            category=    "Missing Clause Risk",
            severity=    "medium" if len(missing) >= 3 else "low",
            title=       "Missing standard protections",
            description= f"Document appears to lack: {', '.join(missing[:3])}",
            reason=      "Missing clauses may leave parties without important protections",
            evidence=    "Standard clauses not found in document text",
            confidence=  0.65,
            source=      RiskSource(
                page_number= chunks[0].get("page_number") if chunks else None,
                chunk_id=    chunks[0]["chunk_id"] if chunks else "unknown",
            )
        ))
    
    # Limit to top 10 risks
    risks = risks[:10]
    
    # Calculate overall assessment
    overall, score, factors = _calculate_overall_risk(risks)
    
    return RiskAssessment(
        overall_risk=        overall,
        risk_score=          score,
        factors=             factors,
        risks=               risks,
        provider_used=       "LexGuard Free Risk Engine",
        analysis_successful= True,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_legal_risks(
    filename:    str,
    doc_type:    str,
    jurisdiction: Optional[str],
    chunks:      List[Dict],  # [{"text": str, "chunk_id": str, "page_number": int|None}]
) -> RiskAssessment:
    """
    Identify legal risks in document chunks with severity and confidence scoring.
    
    IMPORTANT: Provides AI-assisted legal information, NOT definitive legal advice.
    
    Parameters
    ----------
    filename     : original document filename
    doc_type     : DocumentType.value string
    jurisdiction : optional jurisdiction
    chunks       : list of dicts with keys: text, chunk_id, page_number
    
    Returns
    -------
    RiskAssessment with overall risk level, risk score, and individual risks
    """
    if not chunks:
        return RiskAssessment(
            overall_risk=        "Low",
            risk_score=          0.0,
            factors=             ["No text available for risk analysis"],
            risks=               [],
            analysis_successful= False,
            error_message=       "No text chunks available for risk analysis",
        )
    
    full_text = "\n\n".join(c["text"] for c in chunks)[:MAX_TEXT_FOR_RISK_ANALYSIS]
    
    # ── Try Gemini ─────────────────────────────────────────────────────────
    api_key = get_gemini_api_key()
    if _is_valid_gemini_key(api_key):
        try:
            gemini = GeminiService(api_key=api_key)
            parsed = _gemini_risk_analysis(gemini, filename, doc_type,
                                            jurisdiction, full_text)
            if parsed and "risks" in parsed:
                # Build structured results from Gemini response
                risk_objs = []
                for r_dict in parsed.get("risks", []):
                    # Find best matching chunk for source
                    evidence_text = r_dict.get("evidence", "").lower()
                    best_chunk = chunks[0]  # default
                    for chunk in chunks:
                        if any(word in chunk["text"].lower() for word in evidence_text.split()[:5]):
                            best_chunk = chunk
                            break
                    
                    # Validate and normalize
                    severity = r_dict.get("severity", "medium")
                    if severity not in SEVERITY_LEVELS:
                        severity = "medium"
                    
                    category = r_dict.get("category", "Compliance Risk")
                    if category not in RISK_CATEGORIES:
                        category = "Compliance Risk"
                    
                    confidence = r_dict.get("confidence", 0.75)
                    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                        confidence = 0.75
                    
                    risk_objs.append(IdentifiedRisk(
                        category=    category,
                        severity=    severity,
                        title=       r_dict.get("title", "Untitled Risk"),
                        description= r_dict.get("description", ""),
                        reason=      r_dict.get("reason", ""),
                        evidence=    r_dict.get("evidence", "")[:300],
                        confidence=  confidence,
                        source=      RiskSource(
                            page_number= best_chunk.get("page_number"),
                            chunk_id=    best_chunk.get("chunk_id", "unknown"),
                        )
                    ))
                
                overall, score, factors = _calculate_overall_risk(risk_objs)
                
                return RiskAssessment(
                    overall_risk=        overall,
                    risk_score=          score,
                    factors=             factors,
                    risks=               risk_objs[:15],  # limit to 15
                    provider_used=       "Google Gemini AI",
                    analysis_successful= True,
                )
        
        except Exception as exc:
            logger.warning("Gemini risk analysis failed: %s", exc)
    
    # ── Fallback — rule-based engine ───────────────────────────────────────
    return _free_engine_risk_analysis(filename, doc_type, jurisdiction, chunks)
