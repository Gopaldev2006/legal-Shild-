"""
RAG Phase 4 — Context Builder
==============================
Formats retrieved SearchResult objects into a structured prompt context
that Gemini (or the fallback engine) can reason over.

The same formatting is used for both Gemini and the free engine so the
downstream generator receives consistent input.

Output example
--------------
SOURCE 1
Document : Employment_Contract.pdf
Page     : 4
Similarity: 0.91

[chunk text here...]

SOURCE 2
Document : Employment_Contract.pdf
Page     : 5
Similarity: 0.87

[chunk text here...]
"""

from typing import List, Optional
from app.services.retrieval.retrieval_service import SearchResult
from app.core.config import settings

# ── constants ────────────────────────────────────────────────────────────────
# Hard cap so we never blow the Gemini context window
MAX_CHARS_PER_CHUNK = 2000


def build_context(results: List[SearchResult]) -> str:
    """
    Convert a list of SearchResult objects into a formatted context string
    ready to be injected into the generation prompt.

    Parameters
    ----------
    results : top-K SearchResult list, already sorted by similarity desc

    Returns
    -------
    Structured context string.  Returns "" if results is empty.
    """
    if not results:
        return ""

    cap = settings.RAG_MAX_CONTEXT_CHUNKS
    parts: List[str] = []

    for i, r in enumerate(results[:cap], start=1):
        # Truncate very long chunks to protect context window
        text = r.content.strip()
        if len(text) > MAX_CHARS_PER_CHUNK:
            text = text[:MAX_CHARS_PER_CHUNK] + "... [truncated]"

        part = (
            f"SOURCE {i}\n"
            f"Document  : {r.filename}\n"
            f"Page      : {r.page_number or 'N/A'}\n"
            f"Similarity: {r.similarity:.2f}\n"
        )
        if r.matter_id:
            part += f"Matter ID : {r.matter_id}\n"
        if r.jurisdiction:
            part += f"Jurisdiction: {r.jurisdiction}\n"
        part += f"\n{text}"

        parts.append(part)

    return "\n\n---\n\n".join(parts)


def build_system_prompt() -> str:
    """
    Returns the LexGuard RAG system prompt injected into every generation call.
    """
    return (
        "You are LexGuard AI, a professional legal document analysis assistant.\n\n"
        "Your task is to answer the user's question using ONLY the retrieved document "
        "context provided below.\n\n"
        "RULES YOU MUST FOLLOW:\n"
        "1. Base your answer primarily on the retrieved context. Do NOT invent clauses, "
        "sections, or facts not present in the context.\n"
        "2. If the context contains enough information, provide a clear, precise answer "
        "and cite the source document and page number.\n"
        "3. If the context does NOT contain enough information to answer the question, "
        "explicitly say: \"The uploaded document does not contain sufficient information "
        "to answer this question.\"\n"
        "4. Clearly distinguish between document-specific findings and general legal "
        "information. Label general knowledge as [General Legal Information].\n"
        "5. Never fabricate page numbers, citations, or legal references.\n"
        "6. Do not claim certainty when the evidence is incomplete or ambiguous.\n"
        "7. You are not a lawyer. Do not provide formal legal advice. Include a brief "
        "disclaimer where appropriate.\n"
        "8. Keep your answer professional, structured, and concise.\n"
        "9. When quoting or referencing a source, mention the document name and page.\n"
        "10. If multiple sources are relevant, synthesize them coherently.\n\n"
        "FORMAT:\n"
        "- Use markdown headings and bullet points for clarity.\n"
        "- End with a 'Sources' section listing the documents and pages referenced.\n"
        "- Add a one-line legal disclaimer at the end."
    )


def build_full_prompt(query: str, context: str) -> str:
    """
    Combines query + context into the final user-facing prompt string sent
    to Gemini (used for direct REST calls that don't support system_instruction).
    """
    return (
        f"RETRIEVED DOCUMENT CONTEXT:\n\n"
        f"{context}\n\n"
        f"---\n\n"
        f"USER QUESTION:\n{query}\n\n"
        f"Please answer the question using the document context above."
    )
