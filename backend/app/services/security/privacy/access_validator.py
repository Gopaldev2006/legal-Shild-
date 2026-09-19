"""
Access Validation Engine for Data-Leakage Protection.

Enforces pre-retrieval and pre-generation authorization boundaries.
Ensures that no sensitive or unauthorized document context reaches the AI model.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.document import LegalDocument


class AccessValidator:
    """
    Access Validation Engine.
    Executes primary authorization checks BEFORE sensitive data reaches the LLM.
    """

    def validate_matter_access(
        self, user_role: str, user_id: int, matter_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Validates if user has permission to query the specified matter ID.
        """
        if user_role == "PUBLIC_USER":
            return {
                "is_authorized": False,
                "reason": "Public users cannot query private matter contexts.",
            }

        # LEGAL_PROFESSIONAL or ADMIN access
        if matter_id and matter_id.startswith("RESTRICTED_ORGANIZATION_"):
            if user_role != "ADMIN":
                return {
                    "is_authorized": False,
                    "reason": f"User #{user_id} lacks clearance for restricted organization matter '{matter_id}'.",
                }

        return {
            "is_authorized": True,
            "reason": "Authorized matter access.",
        }

    def validate_document_access(
        self, db: Session, user_id: int, user_role: str, document_id: int
    ) -> Dict[str, Any]:
        """
        Verifies document ownership before document inspection or argument extraction.
        """
        if user_role == "ADMIN":
            doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
            if doc:
                return {"is_authorized": True, "document": doc}
            return {"is_authorized": False, "reason": "Document not found."}

        doc = db.query(LegalDocument).filter(
            LegalDocument.id == document_id,
            LegalDocument.owner_id == user_id
        ).first()

        if not doc:
            return {
                "is_authorized": False,
                "reason": f"Access Refused: Document #{document_id} does not exist or belong to User #{user_id}.",
            }

        return {"is_authorized": True, "document": doc}

    def validate_retrieved_chunks(
        self, user_role: str, user_id: int, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        HARD PRE-GENERATION AUTHORIZATION CHECK.
        Verifies 100% of retrieved context chunks strictly belong to the current user (for LEGAL_PROFESSIONAL).
        Purges any unauthorized chunk BEFORE context is formatted or passed to model prompt.
        """
        if user_role == "PUBLIC_USER":
            return []

        if user_role == "ADMIN":
            return chunks

        authorized_chunks = []
        for chunk in chunks:
            owner_id = chunk.get("owner_id")
            if owner_id == user_id:
                authorized_chunks.append(chunk)
            else:
                # Security logging trigger: unauthorized chunk purged before reaching LLM
                print(
                    f"[SECURITY NOTICE] Purged unauthorized chunk belonging to Owner #{owner_id} "
                    f"from User #{user_id}'s RAG context payload."
                )

        return authorized_chunks


access_validator = AccessValidator()
