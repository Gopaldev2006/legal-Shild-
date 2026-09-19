"""
extractor.py — Safe Document Text Extraction
=============================================
Extracts plain text from PDF and DOCX files.

Security rules:
  - Never execute macros, scripts, or embedded programs.
  - Malformed / crafted files are caught and raised as ValueError
    with a safe message (no stack trace or internal path exposed).
  - Only plain text content is returned; binary blobs are discarded.
  - TXT files are read as UTF-8; undecodable bytes are silently replaced.

Supported types:  .pdf  .docx
(TXT support retained for internal/test use but no longer accepted via upload)
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def extract_text_from_document(
    file_path: str,
    file_type: str,
) -> List[Dict[str, Any]]:
    """
    Extract raw text from a PDF or DOCX file.

    Parameters
    ----------
    file_path : absolute path to the stored file
    file_type : canonical file extension WITHOUT the dot,
                e.g. "pdf" or "docx"

    Returns
    -------
    List of page dicts:
        [{"page_number": int, "text": str}, ...]

    Raises
    ------
    ValueError
        Safe, user-facing message on any extraction failure.
        Internal details are logged server-side only.
    """
    file_type = file_type.lower().strip(".")

    if file_type == "pdf":
        return _extract_pdf(file_path)

    if file_type == "docx":
        return _extract_docx(file_path)

    # TXT kept for backward-compat with tests / CLI tools
    if file_type == "txt":
        return _extract_txt(file_path)

    raise ValueError(f"Unsupported file type: {file_type}")


# ── PDF ───────────────────────────────────────────────────────────────────────

def _extract_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Extract text page-by-page from a PDF using pypdf."""
    try:
        import pypdf  # type: ignore
    except ImportError:
        raise ValueError("PDF extraction library (pypdf) is not installed.")

    try:
        reader = pypdf.PdfReader(file_path)
    except Exception as exc:
        logger.warning("PDF open failed for %s: %s", file_path, type(exc).__name__)
        raise ValueError(
            "The PDF file could not be opened. It may be corrupt, password-protected, "
            "or not a valid PDF document."
        ) from None

    pages: List[Dict[str, Any]] = []
    try:
        for idx, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                # A single bad page should not abort the whole document
                logger.warning(
                    "PDF page %d extraction error in %s: %s",
                    idx, file_path, type(exc).__name__,
                )
                page_text = ""

            if page_text.strip():
                pages.append({"page_number": idx, "text": page_text})
    except Exception as exc:
        logger.warning("PDF iteration failed for %s: %s", file_path, type(exc).__name__)
        raise ValueError(
            "The PDF file could not be read. It may be corrupt or use an unsupported format."
        ) from None

    if not pages:
        pages.append({
            "page_number": 1,
            "text": "[Empty or unscannable PDF — no extractable text found]",
        })

    return pages


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _extract_docx(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract text from a DOCX file using python-docx.

    Only paragraph text is extracted. Tables, images, macros, and
    embedded OLE objects are intentionally ignored.
    """
    try:
        import docx  # type: ignore
    except ImportError:
        raise ValueError("DOCX extraction library (python-docx) is not installed.")

    try:
        doc = docx.Document(file_path)
    except Exception as exc:
        logger.warning("DOCX open failed for %s: %s", file_path, type(exc).__name__)
        raise ValueError(
            "The DOCX file could not be opened. It may be corrupt or not a valid "
            "Word document."
        ) from None

    try:
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text  = "\n".join(paragraphs)
    except Exception as exc:
        logger.warning("DOCX paragraph read failed for %s: %s", file_path, type(exc).__name__)
        raise ValueError(
            "The DOCX file could not be read. It may be corrupt or use an unsupported format."
        ) from None

    if not full_text.strip():
        full_text = "[Empty DOCX document — no extractable text found]"

    return [{"page_number": 1, "text": full_text}]


# ── TXT ───────────────────────────────────────────────────────────────────────

def _extract_txt(file_path: str) -> List[Dict[str, Any]]:
    """Read a plain-text file as UTF-8. Undecodable bytes are replaced."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception as exc:
        logger.warning("TXT read failed for %s: %s", file_path, type(exc).__name__)
        raise ValueError("The text file could not be read.") from None

    if not content.strip():
        content = "[Empty TXT document]"

    return [{"page_number": 1, "text": content}]
