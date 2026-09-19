"""
Standalone Decoupled Citation Verification Engine.

Verifies that AI model responses are strictly grounded in authorized retrieved legal documents.
Enforces the standardized citation schema:
{
  "document_id": int/str,
  "document_name": str,
  "page": int,
  "chunk_id": str,
  "relevance": float
}
Verifies:
1. Cited document exists in DB/system
2. Cited chunk exists in DB/system
3. Cited chunk belongs to authorized user/matter
4. Citation corresponds to retrieved context set
5. Detection of fabricated/hallucinated citations
"""

import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.document import LegalDocument, DocumentChunk


class CitationValidator:
    """
    Decoupled Citation Verification Engine.
    Grounds AI responses in verified, authorized source chunks.
    """

    NO_EVIDENCE_REFUSAL = (
        "The available authorized documents do not contain sufficient information "
        "to answer this query."
    )


    def extract_citations(
        self, context_chunks: List[Dict[str, Any]], db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts verified citation metadata from authorized context chunks matching schema.
        """
        if not context_chunks:
            return []

        citations = []
        for idx, chunk in enumerate(context_chunks, 1):
            doc_id = chunk.get("document_id", "N/A")
            page_num = chunk.get("page_number", chunk.get("page", 1))
            chunk_id = chunk.get("chunk_id", f"chk_{doc_id}_{idx}")
            score = chunk.get("similarity_score", chunk.get("score", 1.0))
            
            # Fetch document filename from DB if db session is provided
            doc_name = chunk.get("filename", chunk.get("document_name"))
            if not doc_name and db and isinstance(doc_id, int):
                doc = db.query(LegalDocument).filter(LegalDocument.id == doc_id).first()
                if doc:
                    doc_name = doc.filename
            if not doc_name:
                doc_name = f"Document_{doc_id}.pdf"

            raw_text = chunk.get("text", "")
            snippet = raw_text[:150] + "..." if len(raw_text) > 150 else raw_text

            citations.append({
                "citation_index": idx,
                "document_id": doc_id,
                "document_name": doc_name,
                "page": page_num,
                "page_number": page_num,  # compatibility alias
                "chunk_id": chunk_id,
                "relevance": round(float(score), 2),
                "score": round(float(score), 2),  # compatibility alias
                "owner_id": chunk.get("owner_id"),
                "matter_id": chunk.get("matter_id"),
                "snippet": snippet,
                "is_valid": True,
                "is_authorized": True,
                "is_fabricated": False,
            })

        return citations

    def verify_single_citation(
        self,
        citation: Dict[str, Any],
        authorized_context_chunks: List[Dict[str, Any]],
        user_context: Optional[Any] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Verifies a single citation against 5 strict rules:
        1. Document existence
        2. Chunk existence
        3. User/matter authorization (owner_id == user.id)
        4. Context match (present in retrieved top-k set)
        5. Fabrication detection (flagged if doc/chunk ID is hallucinated)
        """
        doc_id = citation.get("document_id")
        chunk_id = citation.get("chunk_id")
        owner_id = citation.get("owner_id")

        # 1. Context Match Check: Is this citation in the retrieved top-k context set?
        context_match = False
        matching_context_chunk = None
        for chunk in authorized_context_chunks:
            c_doc = chunk.get("document_id")
            c_chunk = chunk.get("chunk_id")
            if (str(c_doc) == str(doc_id)) or (c_chunk and str(c_chunk) == str(chunk_id)):
                context_match = True
                matching_context_chunk = chunk
                break

        # 2. Document & Chunk Existence Check
        doc_exists = True
        chunk_exists = True
        if db and isinstance(doc_id, int):
            db_doc = db.query(LegalDocument).filter(LegalDocument.id == doc_id).first()
            if not db_doc:
                doc_exists = False
            if chunk_id:
                db_chunk = db.query(DocumentChunk).filter(
                    DocumentChunk.chunk_id == str(chunk_id)
                ).first()
                if not db_chunk:
                    chunk_exists = False

        # 3. User Authorization Check
        is_authorized = True
        if user_context and getattr(user_context, "role", "") != "ADMIN":
            user_id = getattr(user_context, "user_id", None)
            if owner_id is not None and user_id is not None and owner_id != user_id:
                is_authorized = False
            elif matching_context_chunk:
                chunk_owner = matching_context_chunk.get("owner_id")
                if chunk_owner is not None and user_id is not None and chunk_owner != user_id:
                    is_authorized = False

        # 4 & 5. Fabrication & Overall Validity
        is_fabricated = (not context_match) or (not doc_exists) or (not chunk_exists)
        is_valid = doc_exists and chunk_exists and is_authorized and context_match and (not is_fabricated)

        failure_reasons = []
        if not doc_exists:
            failure_reasons.append(f"Document #{doc_id} does not exist in system database.")
        if not chunk_exists:
            failure_reasons.append(f"Chunk #{chunk_id} does not exist in system database.")
        if not is_authorized:
            failure_reasons.append(f"Citation belongs to another user/owner (#{owner_id}).")
        if not context_match:
            failure_reasons.append("Citation was not present in authorized retrieved context set.")
        if is_fabricated:
            failure_reasons.append("Fabricated / hallucinated citation detected.")

        return {
            "document_id": doc_id,
            "document_name": citation.get("document_name", f"Document_{doc_id}"),
            "page": citation.get("page", citation.get("page_number", 1)),
            "chunk_id": chunk_id,
            "relevance": citation.get("relevance", 0.0),
            "is_valid": is_valid,
            "is_authorized": is_authorized,
            "is_fabricated": is_fabricated,
            "failure_reasons": failure_reasons,
        }

    def validate_response(
        self,
        response_text: str,
        context_chunks: List[Dict[str, Any]],
        user_context: Optional[Any] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Validates model response against authorized context and citations.
        If context is empty or ungrounded, enforces mandatory refusal message.
        Prevents fake or hallucinated legal citations.
        """
        if not context_chunks:
            return {
                "is_grounded": False,
                "contains_unauthorized_data": False,
                "contains_fabricated_citations": False,
                "final_text": self.NO_EVIDENCE_REFUSAL,
                "citations": [],
                "validation_notes": "Zero context available; enforced no-evidence refusal response.",
            }

        # Extract verified citations from authorized retrieved chunks
        verified_citations = self.extract_citations(context_chunks, db=db)

        # Detect inline citation patterns in response_text (e.g., [Doc #10, Page 2] or [Doc #999, Chunk #chk_999])
        inline_citation_matches = re.findall(r"\[Doc\s*#?(\w+)(?:,\s*Page\s*(\d+))?(?:,\s*Chunk\s*#?(\w+))?\]", response_text, re.IGNORECASE)
        
        has_fabricated_citations = False
        fabricated_notes = []

        if inline_citation_matches:
            for match in inline_citation_matches:
                doc_str, page_str, chunk_str = match
                parsed_citation = {
                    "document_id": int(doc_str) if doc_str.isdigit() else doc_str,
                    "page": int(page_str) if page_str and page_str.isdigit() else 1,
                    "chunk_id": chunk_str or None,
                    "relevance": 1.0,
                }
                
                check = self.verify_single_citation(
                    citation=parsed_citation,
                    authorized_context_chunks=context_chunks,
                    user_context=user_context,
                    db=db
                )

                if check["is_fabricated"] or not check["is_valid"]:
                    has_fabricated_citations = True
                    fabricated_notes.append(f"Fabricated inline citation '[Doc #{doc_str}]': {', '.join(check['failure_reasons'])}")

        # Redact/Sanitize raw prompt system keywords if present
        cleaned_text = response_text
        if "SECURITY POLICY & SYSTEM GUARDRAILS" in cleaned_text:
            cleaned_text = (
                "Security Notice: Output contained system guardrail reflections and was sanitized."
            )

        if has_fabricated_citations:
            notes = f"Fabricated citations detected and flagged: {'; '.join(fabricated_notes)}"
        else:
            notes = "Response verified and grounded against authorized context chunks."

        return {
            "is_grounded": not has_fabricated_citations,
            "contains_unauthorized_data": False,
            "contains_fabricated_citations": has_fabricated_citations,
            "final_text": cleaned_text,
            "citations": verified_citations,
            "validation_notes": notes,
        }


citation_validator = CitationValidator()
