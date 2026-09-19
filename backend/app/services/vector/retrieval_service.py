from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from app.services.vector.embedding_service import generate_embedding
from app.services.vector.vector_repository import vector_repo


@dataclass
class UserContext:
    user_id: int
    role: str  # PUBLIC_USER, LEGAL_PROFESSIONAL, ADMIN


class RetrievalService:
    """
    Permission-Aware Vector Retrieval Service.
    Enforces authorization filtering DURING vector search.
    A user will NEVER receive a chunk merely because it is semantically similar
    unless they are explicitly authorized to access it.
    """
    def search(
        self,
        query: str,
        user_context: UserContext,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Executes permission-aware semantic search over vector store.
        - PUBLIC_USER: Always returns [] (Zero access to RAG vector database).
        - LEGAL_PROFESSIONAL: Strictly filtered to vectors where owner_id == user_context.user_id.
        - ADMIN: Full search access, optionally filtered by user_id or metadata.
        """
        if not query or not query.strip():
            return []

        # Security Boundary Rule 1: PUBLIC_USER has zero access to RAG vector store
        if user_context.role == "PUBLIC_USER":
            return []

        # 1. Generate query vector embedding
        query_vector = generate_embedding(query)

        # 2. Define authorization metadata filter callback
        def authorization_filter(meta: Dict[str, Any]) -> bool:
            # Security Boundary Rule 2: LEGAL_PROFESSIONAL can only access own documents
            if user_context.role == "LEGAL_PROFESSIONAL":
                if meta.get("owner_id") != user_context.user_id:
                    return False

            # Security Boundary Rule 3: ADMIN can optionally filter by owner_id if specified in filters
            if user_context.role == "ADMIN" and filters and "owner_id" in filters:
                if meta.get("owner_id") != filters["owner_id"]:
                    return False

            # Optional Metadata Filters (document_type, matter_id, source_type)
            if filters:
                if "document_type" in filters and filters["document_type"]:
                    if meta.get("document_type") != filters["document_type"]:
                        return False
                if "matter_id" in filters and filters["matter_id"]:
                    if meta.get("matter_id") != filters["matter_id"]:
                        return False
                if "source_type" in filters and filters["source_type"]:
                    if meta.get("source_type") != filters["source_type"]:
                        return False

            return True

        # 3. Perform vector search enforcing filter DURING retrieval
        results = vector_repo.search_vectors(
            query_vector=query_vector,
            top_k=top_k,
            filter_fn=authorization_filter
        )

        return results


retrieval_service = RetrievalService()
