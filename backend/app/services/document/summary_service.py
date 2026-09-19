"""
Document Summarization Service — Phase 2
==========================================
Produces a structured 6-field summary of a legal document.

Fields
------
1. executive_summary  — concise plain-English overview (3-5 sentences)
2. document_type      — contract / court order / statute / NDA / etc.
3. purpose            — what the document is intended to achieve
4. main_subject       — the central topic or matter the document concerns
5. key_takeaways      — 3-7 bullet points of critical information
6. sources            — which chunks contributed (page_number, chunk_id)

Hierarchical summarization
--------------------------
For long documents (> CHUNK_SUMMARY_THRESHOLD chars) we:
  1. Summarise each chunk independently (chunk-level pass)
  2. Combine chunk summaries into a single synthesis prompt (doc-level pass)

For short documents we do a single-pass summary.

Reuses existing GeminiService and free_ai_service — no new AI integration.

Security
--------
Caller must pass only chunks already filtered by owner_id.
This service does NOT re-query the database.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from app.services.ai.gemini_service import GeminiService, get_gemini_api_key

logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────
CHUNK_SUMMARY_THRESHOLD = 3000   # chars: above this → hierarchical mode
MAX_CHUNK_CHARS         = 1500   # max chars per chunk in hierarchical pass
MAX_SINGLE_PASS_CHARS   = 10000  # max chars for single-pass summary


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class SummarySource:
    page_number: Optional[int]
    chunk_id:    str


@dataclass
class SummaryResult:
    executive_summary: str                    = ""
    document_type:     str                    = "Not specified"
    purpose:           str                    = "Not clearly specified in the document."
    main_subject:      str                    = "Not clearly specified in the document."
    key_takeaways:     List[str]              = field(default_factory=list)
    sources:           List[SummarySource]    = field(default_factory=list)
    provider_used:     str                    = "LexGuard Free Summary Engine"
    successful:        bool                   = True
    error_message:     Optional[str]          = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_valid_gemini_key(key: str) -> bool:
    return bool(key) and key.startswith("AIzaSy")


def _parse_json_response(raw: str) -> Optional[Dict[str, Any]]:
    """Robustly extract JSON from Gemini response (handles markdown fences)."""
    if not raw:
        return None
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:] if len(lines) > 2 else lines
        text  = "\n".join(inner[:-1] if inner[-1].strip() == "```" else inner)
    try:
        return json.loads(text.strip())
    except Exception:
        try:
            start = text.index("{")
            end   = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return None


# ── prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are LexGuard AI, a professional legal document summarization assistant. "
    "You produce structured, accurate summaries grounded entirely in the document text. "
    "Never invent facts, dates, names, or clauses not present in the source text. "
    "When information is absent, write exactly: \"Not clearly specified in the document.\" "
    "Always return valid JSON only — no markdown, no extra text."
)


def _single_pass_prompt(filename: str, doc_type: str,
                         jurisdiction: Optional[str], text: str) -> str:
    meta = f"Filename: {filename}\nDocument Type: {doc_type}"
    if jurisdiction:
        meta += f"\nJurisdiction: {jurisdiction}"
    return f"""You are LexGuard AI. Analyse the legal document below and return a JSON summary.

Return EXACTLY this JSON structure:
{{
  "executive_summary": "3-5 sentence plain-English overview of the entire document",
  "document_type": "type of legal document (e.g. Service Agreement, Employment Contract, NDA, Court Order)",
  "purpose": "1-2 sentences on what this document is intended to achieve",
  "main_subject": "1 sentence on the central topic or matter the document concerns",
  "key_takeaways": [
    "Critical point 1 from the document",
    "Critical point 2 from the document",
    "Critical point 3 from the document"
  ]
}}

STRICT RULES:
- Return ONLY valid JSON. No markdown fences, no explanation outside JSON.
- Base everything strictly on the document text below.
- Do NOT invent any clause, date, party name, or obligation.
- If a field cannot be determined from the text, use exactly: "Not clearly specified in the document."
- key_takeaways must have 3-7 items, each 1-2 sentences.
- Preserve important legal terminology exactly as it appears in the document.

DOCUMENT METADATA:
{meta}

DOCUMENT TEXT:
{text}

Return JSON now:"""


def _chunk_summary_prompt(chunk_text: str, chunk_index: int) -> str:
    return f"""Summarise the following section (Section {chunk_index + 1}) of a legal document in 2-3 sentences.
Focus on: parties mentioned, key obligations, dates, clauses, and legal terms.
Return ONLY the summary text — no JSON, no headers.

SECTION TEXT:
{chunk_text}

Summary:"""


def _combine_summaries_prompt(filename: str, doc_type: str,
                               jurisdiction: Optional[str],
                               chunk_summaries: List[str]) -> str:
    meta = f"Filename: {filename}\nDocument Type: {doc_type}"
    if jurisdiction:
        meta += f"\nJurisdiction: {jurisdiction}"

    combined = "\n\n".join(
        f"Section {i+1}: {s}" for i, s in enumerate(chunk_summaries)
    )
    return f"""You are LexGuard AI. The following are section-by-section summaries of a legal document.
Synthesise them into a comprehensive structured JSON summary.

Return EXACTLY this JSON structure:
{{
  "executive_summary": "3-5 sentence synthesis of the entire document",
  "document_type": "type of legal document",
  "purpose": "1-2 sentences on the document's purpose",
  "main_subject": "1 sentence on the central topic",
  "key_takeaways": [
    "Critical point 1",
    "Critical point 2",
    "Critical point 3"
  ]
}}

STRICT RULES:
- Return ONLY valid JSON.
- Base everything on the section summaries provided.
- Do NOT invent facts not present in the summaries.
- If a field cannot be determined, write: "Not clearly specified in the document."
- key_takeaways: 3-7 items.

DOCUMENT METADATA:
{meta}

SECTION SUMMARIES:
{combined}

Return JSON now:"""


# ── Gemini summarization ──────────────────────────────────────────────────────

def _gemini_single_pass(gemini: GeminiService, filename: str, doc_type: str,
                         jurisdiction: Optional[str], text: str) -> Optional[Dict]:
    raw = gemini.generate_response(
        prompt=             _single_pass_prompt(filename, doc_type, jurisdiction, text),
        system_instruction= _SYSTEM_PROMPT,
        temperature=        0.1,
    )
    if not raw or raw.startswith("[Google Gemini API Error"):
        return None
    return _parse_json_response(raw)


def _gemini_chunk_summary(gemini: GeminiService, chunk_text: str,
                           chunk_index: int) -> Optional[str]:
    """Summarise a single chunk — returns plain text, not JSON."""
    raw = gemini.generate_response(
        prompt=      _chunk_summary_prompt(chunk_text, chunk_index),
        temperature= 0.1,
    )
    if not raw or raw.startswith("[Google Gemini API Error"):
        return None
    return raw.strip()[:500]


def _gemini_hierarchical(gemini: GeminiService, filename: str, doc_type: str,
                          jurisdiction: Optional[str],
                          chunks: List[Dict]) -> Optional[Dict]:
    """
    Two-pass:
    1. Summarise each chunk independently.
    2. Combine chunk summaries into final structured JSON.
    """
    chunk_summaries = []
    for i, chk in enumerate(chunks):
        text = chk["text"][:MAX_CHUNK_CHARS]
        cs   = _gemini_chunk_summary(gemini, text, i)
        if cs:
            chunk_summaries.append(cs)
        else:
            # fallback: use first 200 chars of chunk as its summary
            chunk_summaries.append(text[:200].strip())

    if not chunk_summaries:
        return None

    raw = gemini.generate_response(
        prompt=             _combine_summaries_prompt(filename, doc_type,
                                                      jurisdiction, chunk_summaries),
        system_instruction= _SYSTEM_PROMPT,
        temperature=        0.1,
    )
    if not raw or raw.startswith("[Google Gemini API Error"):
        return None
    return _parse_json_response(raw)


# ── Free engine fallback ──────────────────────────────────────────────────────

def _free_engine_summary(filename: str, doc_type: str,
                          jurisdiction: Optional[str],
                          chunks: List[Dict]) -> SummaryResult:
    """
    Rule-based fallback summary extractor.
    Uses regex + keyword heuristics to produce a structured summary.
    """
    full_text = "\n\n".join(c["text"] for c in chunks)
    lines     = [l.strip() for l in full_text.split("\n") if l.strip()]
    lower     = full_text.lower()

    # ── Executive summary ─────────────────────────────────────────────────
    intro = " ".join(lines[:8])[:500]
    doc_name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    executive_summary = (
        f"This document is a {doc_name}. "
        f"{intro[:300]}{'...' if len(intro) > 300 else ''}"
    )

    # ── Document type ─────────────────────────────────────────────────────
    detected_type = doc_type.replace("_", " ").title() if doc_type else "Legal Document"
    type_keywords = {
        "agreement":    "Agreement",
        "contract":     "Contract",
        "nda":          "Non-Disclosure Agreement",
        "employment":   "Employment Agreement",
        "service":      "Service Agreement",
        "lease":        "Lease Agreement",
        "court":        "Court Order",
        "judgment":     "Court Judgment",
        "statute":      "Statute / Legislation",
        "petition":     "Legal Petition",
        "affidavit":    "Affidavit",
        "deed":         "Legal Deed",
        "will":         "Will / Testament",
        "mou":          "Memorandum of Understanding",
        "amendment":    "Amendment",
    }
    for kw, label in type_keywords.items():
        if kw in lower or kw in filename.lower():
            detected_type = label
            break

    # ── Purpose ───────────────────────────────────────────────────────────
    purpose_patterns = [
        r'purpose\s+of\s+this\s+(?:agreement|contract|document)[^\.]+\.',
        r'this\s+(?:agreement|contract|document)\s+(?:is\s+entered|governs|establishes)[^\.]+\.',
        r'witnesseth[^\.]+\.',
    ]
    purpose = "Not clearly specified in the document."
    for pat in purpose_patterns:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            purpose = m.group().strip()[:300]
            break
    if purpose == "Not clearly specified in the document." and lines:
        # Use second paragraph as purpose hint
        for line in lines[3:10]:
            if len(line) > 40:
                purpose = line[:250]
                break

    # ── Main subject ──────────────────────────────────────────────────────
    subject_keywords = ["concerning", "regarding", "relating to", "in the matter of",
                        "subject:", "re:", "this agreement covers"]
    main_subject = "Not clearly specified in the document."
    for kw in subject_keywords:
        idx = lower.find(kw)
        if idx != -1:
            main_subject = full_text[idx: idx + 200].strip()[:200]
            break
    if main_subject == "Not clearly specified in the document.":
        main_subject = f"Legal matter pertaining to {doc_name}"

    # ── Key takeaways ─────────────────────────────────────────────────────
    takeaway_signals = [
        (r'\d+\s+days?\s+(?:written\s+)?notice',       "Notice period: {}"),
        (r'terminat[^\.\n]{0,100}\.',                   "Termination: {}"),
        (r'confidential[^\.\n]{0,100}\.',               "Confidentiality: {}"),
        (r'payment[^\.\n]{0,100}\.',                    "Payment: {}"),
        (r'governing\s+law[^\.\n]{0,100}\.',            "Governing law: {}"),
        (r'arbitrat[^\.\n]{0,100}\.',                   "Dispute resolution: {}"),
        (r'liability[^\.\n]{0,100}\.',                  "Liability: {}"),
        (r'intellectual\s+property[^\.\n]{0,100}\.',    "IP clause: {}"),
    ]
    key_takeaways = []
    for pat, template in takeaway_signals:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            snippet = m.group().strip()[:150]
            key_takeaways.append(snippet)
        if len(key_takeaways) >= 7:
            break

    if not key_takeaways:
        key_takeaways = [
            "Review the document manually for key terms and conditions.",
            "Verify all party names, obligations, and deadlines.",
            "Consult a qualified legal professional for formal interpretation.",
        ]

    return SummaryResult(
        executive_summary= executive_summary,
        document_type=     detected_type,
        purpose=           purpose,
        main_subject=      main_subject,
        key_takeaways=     key_takeaways[:7],
        sources=           [],
        provider_used=     "LexGuard Free Summary Engine",
        successful=        True,
    )


# ── public API ────────────────────────────────────────────────────────────────

def summarize_document(
    filename:    str,
    doc_type:    str,
    jurisdiction: Optional[str],
    chunks:      List[Dict],   # list of {"text": str, "chunk_id": str, "page_number": int|None}
) -> SummaryResult:
    """
    Entry point — produce a structured SummaryResult from document chunks.

    Parameters
    ----------
    filename     : original document filename
    doc_type     : DocumentType.value string
    jurisdiction : optional jurisdiction string
    chunks       : list of dicts with keys: text, chunk_id, page_number

    Returns
    -------
    SummaryResult with 6 structured fields + sources
    """
    if not chunks:
        return SummaryResult(
            executive_summary= "Document has no extractable text.",
            document_type=     doc_type or "Unknown",
            purpose=           "Not clearly specified in the document.",
            main_subject=      "Not clearly specified in the document.",
            key_takeaways=     ["Document could not be summarised — no text available."],
            sources=           [],
            successful=        False,
            error_message=     "No text chunks available",
        )

    # Build sources from all chunks
    sources = [
        SummarySource(
            page_number= chk.get("page_number"),
            chunk_id=    chk.get("chunk_id", ""),
        )
        for chk in chunks
    ]

    full_text  = "\n\n".join(c["text"] for c in chunks)
    is_long    = len(full_text) > CHUNK_SUMMARY_THRESHOLD
    api_key    = get_gemini_api_key()

    # ── Try Gemini ─────────────────────────────────────────────────────────
    if _is_valid_gemini_key(api_key):
        try:
            gemini = GeminiService(api_key=api_key)

            if is_long:
                logger.info("Summarization: hierarchical mode (%d chars)", len(full_text))
                parsed = _gemini_hierarchical(gemini, filename, doc_type, jurisdiction, chunks)
            else:
                logger.info("Summarization: single-pass mode (%d chars)", len(full_text))
                text_for_summary = full_text[:MAX_SINGLE_PASS_CHARS]
                parsed = _gemini_single_pass(gemini, filename, doc_type,
                                              jurisdiction, text_for_summary)

            if parsed:
                return SummaryResult(
                    executive_summary= str(parsed.get("executive_summary", "")).strip()
                                       or "Not clearly specified in the document.",
                    document_type=     str(parsed.get("document_type", doc_type)).strip()
                                       or doc_type,
                    purpose=           str(parsed.get("purpose", "")).strip()
                                       or "Not clearly specified in the document.",
                    main_subject=      str(parsed.get("main_subject", "")).strip()
                                       or "Not clearly specified in the document.",
                    key_takeaways=     [str(t) for t in parsed.get("key_takeaways", []) if t][:7],
                    sources=           sources,
                    provider_used=     "Google Gemini AI",
                    successful=        True,
                )
        except Exception as exc:
            logger.warning("Gemini summarization failed: %s", exc)

    # ── Fallback — rule-based engine ───────────────────────────────────────
    result         = _free_engine_summary(filename, doc_type, jurisdiction, chunks)
    result.sources = sources
    return result
