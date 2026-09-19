"""
Legal-Aware Document Chunker
============================
Replaces the old arbitrary sliding-window splitter.

Design goals
------------
1. Preserve legal section / article / clause boundaries.
2. Prefer splitting on paragraph breaks, then sentence breaks.
3. Never split in the middle of a legal heading or citation.
4. Respect configurable chunk_size & chunk_overlap from settings.
5. Track start_char / end_char offsets and estimate token_count.
6. Return complete metadata per chunk for Phase 2 embedding.

Ownership chain honoured by callers:
    User → LegalDocument → DocumentChunk
"""

import re
import uuid
import json
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.services.document.cleaner import clean_legal_text


# ---------------------------------------------------------------------------
# Regex patterns for legal document structure
# ---------------------------------------------------------------------------

# Matches: "Section 3", "Sec. 12", "Article 14", "Art. 21", "Clause 4.2",
#           "ARTICLE XIV", "SECTION 2A", "Part III", "Chapter IV"
_LEGAL_HEADING = re.compile(
    r'^(?:'
    r'SECTION\s+\d+[A-Z]?|Section\s+\d+[A-Z]?|Sec\.\s*\d+[A-Z]?|'
    r'ARTICLE\s+(?:\d+[A-Z]?|[IVXLCDM]+)|Article\s+(?:\d+[A-Z]?|[IVXLCDM]+)|Art\.\s*\d+[A-Z]?|'
    r'CLAUSE\s+\d+[\.\d]*|Clause\s+\d+[\.\d]*|'
    r'PART\s+(?:\d+|[IVXLCDM]+)|Part\s+(?:\d+|[IVXLCDM]+)|'
    r'CHAPTER\s+(?:\d+|[IVXLCDM]+)|Chapter\s+(?:\d+|[IVXLCDM]+)|'
    r'SCHEDULE\s+\d+|Schedule\s+\d+|'
    r'WHEREAS|WITNESSETH|DEFINITIONS?|OBLIGATIONS?|REPRESENTATIONS?|'
    r'WARRANTIES?|TERMINATION|JURISDICTION|GOVERNING\s+LAW|'
    r'INDEMNIF(?:Y|ICATION)|CONFIDENTIALITY|MISCELLANEOUS|RECITALS?'
    r')[\s:—–-]?',
    re.IGNORECASE | re.MULTILINE,
)

# Matches numbered list items: "1.", "1)", "(a)", "(i)", "a."
_LIST_ITEM = re.compile(
    r'^\s*(?:\d+\.|[a-z]\.|[ivxlcdm]+\.|[\(\[]\s*(?:\d+|[a-z]|[ivxlcdm]+)\s*[\)\]])\s',
    re.IGNORECASE | re.MULTILINE,
)

# Sentence-ending punctuation
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (GPT-style)."""
    return max(1, len(text) // 4)


def _split_into_paragraphs(text: str) -> List[str]:
    """Split on blank lines, keeping non-empty paragraphs."""
    paragraphs = re.split(r'\n\s*\n', text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_into_sentences(text: str) -> List[str]:
    """Split paragraph into sentences, preserving legal citations."""
    # Protect common abbreviations that look like sentence ends
    protected = re.sub(
        r'\b(Mr|Mrs|Dr|Prof|St|vs|viz|etc|No|Art|Sec|Cl|Sch|Vol|Ltd|Inc|Corp)\.',
        r'\1<DOT>',
        text,
    )
    parts = _SENTENCE_END.split(protected)
    return [p.replace('<DOT>', '.').strip() for p in parts if p.strip()]


def _is_legal_heading(line: str) -> bool:
    return bool(_LEGAL_HEADING.match(line.strip()))


# ---------------------------------------------------------------------------
# Core chunker
# ---------------------------------------------------------------------------

def _build_chunks_from_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """
    Splits *text* into overlapping chunks while preserving legal boundaries.

    Strategy (priority order):
    1. If text ≤ chunk_size  → single chunk.
    2. Try to split on legal section headings first.
    3. Fall back to paragraph boundaries.
    4. Fall back to sentence boundaries.
    5. Last resort: hard character split with overlap.

    Returns list of dicts:
        {"text": str, "start_char": int, "end_char": int}
    """
    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [{"text": text, "start_char": 0, "end_char": len(text)}]

    # ── 1. Try section-level splitting ──────────────────────────────────────
    chunks = _split_on_legal_sections(text, chunk_size, chunk_overlap)
    if chunks:
        return chunks

    # ── 2. Paragraph-level splitting ────────────────────────────────────────
    paragraphs = _split_into_paragraphs(text)
    return _merge_segments(paragraphs, text, chunk_size, chunk_overlap)


def _split_on_legal_sections(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """
    Finds legal-heading boundaries and produces one-section-per-chunk groups,
    merging small sections until chunk_size is reached.
    Returns [] if no headings found (caller falls back to paragraph split).
    """
    lines = text.splitlines(keepends=True)
    section_starts: List[int] = []   # line indices that start a new section

    for i, line in enumerate(lines):
        if _is_legal_heading(line):
            section_starts.append(i)

    if not section_starts:
        return []

    # Build section texts
    sections: List[str] = []
    for idx, start in enumerate(section_starts):
        end = section_starts[idx + 1] if idx + 1 < len(section_starts) else len(lines)
        sections.append("".join(lines[start:end]).strip())

    # Merge small adjacent sections so each chunk is close to chunk_size
    return _merge_segments(sections, text, chunk_size, chunk_overlap)


def _merge_segments(
    segments: List[str],
    full_text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """
    Greedily merges segments into chunks ≤ chunk_size.
    When a single segment exceeds chunk_size, splits it by sentence then hard.
    Adds overlap by appending the start of the next segment.
    """
    result: List[Dict[str, Any]] = []
    current_parts: List[str] = []
    current_len = 0
    search_start = 0   # for locating start_char in full_text

    def _flush(parts: List[str]) -> Optional[Dict[str, Any]]:
        combined = "\n\n".join(parts).strip()
        if not combined:
            return None
        start = full_text.find(combined[:50], search_start)
        if start == -1:
            start = 0
        end = start + len(combined)
        return {"text": combined, "start_char": start, "end_char": end}

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        # Segment itself is too big — recursively split by sentence then hard
        if len(seg) > chunk_size:
            # flush current accumulator first
            if current_parts:
                chunk = _flush(current_parts)
                if chunk:
                    result.append(chunk)
                current_parts = []
                current_len = 0

            # split oversized segment
            sub_chunks = _split_by_sentence_then_hard(seg, full_text, chunk_size, chunk_overlap)
            result.extend(sub_chunks)
            continue

        if current_len + len(seg) + 2 > chunk_size and current_parts:
            # flush
            chunk = _flush(current_parts)
            if chunk:
                result.append(chunk)
            # overlap: keep last segment if it fits
            if len(current_parts[-1]) < chunk_overlap:
                current_parts = [current_parts[-1]]
                current_len = len(current_parts[0])
            else:
                current_parts = []
                current_len = 0

        current_parts.append(seg)
        current_len += len(seg) + 2   # +2 for "\n\n"

    if current_parts:
        chunk = _flush(current_parts)
        if chunk:
            result.append(chunk)

    return result


def _split_by_sentence_then_hard(
    text: str,
    full_text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """Split by sentence; if a sentence is still too big, do hard char split."""
    sentences = _split_into_sentences(text)
    result: List[Dict[str, Any]] = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        if len(sent) > chunk_size:
            # Hard split with overlap
            if current:
                start = full_text.find(current[:50])
                if start == -1: start = 0
                result.append({"text": current.strip(), "start_char": start, "end_char": start + len(current)})
                current = ""
            pos = 0
            while pos < len(sent):
                end = min(pos + chunk_size, len(sent))
                piece = sent[pos:end].strip()
                if piece:
                    s = full_text.find(piece[:50])
                    if s == -1: s = 0
                    result.append({"text": piece, "start_char": s, "end_char": s + len(piece)})
                if end == len(sent):
                    break
                pos += chunk_size - chunk_overlap
            continue

        if len(current) + len(sent) + 1 > chunk_size and current:
            start = full_text.find(current[:50])
            if start == -1: start = 0
            result.append({"text": current.strip(), "start_char": start, "end_char": start + len(current)})
            # overlap
            current = current[-chunk_overlap:] + " " + sent if len(current) > chunk_overlap else sent
        else:
            current = (current + " " + sent).strip() if current else sent

    if current.strip():
        start = full_text.find(current[:50])
        if start == -1: start = 0
        result.append({"text": current.strip(), "start_char": start, "end_char": start + len(current)})

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_chunks(
    extracted_pages: List[Dict[str, Any]],
    doc_metadata: Dict[str, Any],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Entry point called by the document upload pipeline.

    Parameters
    ----------
    extracted_pages : list of {"page_number": int, "text": str}
    doc_metadata    : {"doc_id", "filename", "document_type",
                        "jurisdiction", "matter_id"}
    chunk_size      : override (defaults to settings.RAG_CHUNK_SIZE)
    chunk_overlap   : override (defaults to settings.RAG_CHUNK_OVERLAP)

    Returns
    -------
    list of chunk dicts ready for DocumentChunk ORM objects:
        chunk_id, text, page_number, chunk_index,
        start_char, end_char, token_count, source_metadata
    """
    _chunk_size    = chunk_size    or settings.RAG_CHUNK_SIZE
    _chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
    doc_id         = doc_metadata.get("doc_id", "doc")

    result: List[Dict[str, Any]] = []
    global_index = 0

    for page_data in extracted_pages:
        page_num  = page_data.get("page_number", 1)
        raw_text  = page_data.get("text", "")
        clean_txt = clean_legal_text(raw_text)

        if not clean_txt:
            continue

        raw_chunks = _build_chunks_from_text(clean_txt, _chunk_size, _chunk_overlap)

        for rc in raw_chunks:
            chunk_text = rc["text"]
            if not chunk_text:
                continue

            chunk_uuid = f"chk_{doc_id}_{global_index}_{uuid.uuid4().hex[:8]}"
            token_cnt  = _estimate_tokens(chunk_text)

            metadata = {
                "filename":      doc_metadata.get("filename"),
                "document_type": doc_metadata.get("document_type"),
                "jurisdiction":  doc_metadata.get("jurisdiction"),
                "matter_id":     doc_metadata.get("matter_id"),
                "page_number":   page_num,
                "chunk_index":   global_index,
                "char_length":   len(chunk_text),
                "token_estimate": token_cnt,
            }

            result.append({
                "chunk_id":        chunk_uuid,
                "text":            chunk_text,
                "page_number":     page_num,
                "chunk_index":     global_index,
                "start_char":      rc.get("start_char"),
                "end_char":        rc.get("end_char"),
                "token_count":     token_cnt,
                "source_metadata": json.dumps(metadata),
            })
            global_index += 1

    return result
