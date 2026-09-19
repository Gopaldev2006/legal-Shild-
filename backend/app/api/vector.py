from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.core.permissions import require_professional
from app.models.user import User, UserRole
from app.models.document import LegalDocument
from app.services.vector.vector_repository import vector_repo
from app.services.vector.indexing_service import index_document_chunks, reindex_all_documents
from app.services.vector.retrieval_service import retrieval_service, UserContext

router = APIRouter()


class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query string")
    top_k: int = Field(5, ge=1, le=20, description="Number of semantically similar chunks to return")
    document_type: Optional[str] = None
    matter_id: Optional[str] = None


@router.post("/search", summary="Permission-Aware Vector Semantic Search")
def search_vectors(
    req: SearchQueryRequest,
    current_user: User = Depends(require_professional),  # 403 for public users
):
    """
    Executes permission-aware vector semantic search over authorized legal document chunks.
    Requires Verified Legal Professional or Admin.
    """
    user_ctx = UserContext(
        user_id=current_user.id,
        role=current_user.role.value
    )

    filters = {}
    if req.document_type:
        filters["document_type"] = req.document_type
    if req.matter_id:
        filters["matter_id"] = req.matter_id

    results = retrieval_service.search(
        query=req.query,
        user_context=user_ctx,
        filters=filters,
        top_k=req.top_k
    )

    return {
        "query": req.query,
        "results_count": len(results),
        "results": results
    }


@router.post("/index-document/{document_id}", summary="Index Document Chunks into Vector Store")
def index_document(
    document_id: int,
    current_user: User = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Indexes all text chunks of a specified document into the vector store.
    Restricted to document owner or Admin.
    """
    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.owner_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You can only index your own documents"
        )

    try:
        count = index_document_chunks(db, document_id)
        return {
            "message": f"Successfully indexed {count} vector chunks for document '{doc.filename}'",
            "document_id": doc.id,
            "indexed_chunks": count
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/document/{document_id}", summary="Delete Document Vectors from Store")
def delete_document_vectors(
    document_id: int,
    current_user: User = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Deletes vectors associated with document_id from the vector store.
    Restricted to document owner or Admin.
    """
    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.owner_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You can only delete your own document vectors"
        )

    vector_repo.delete_by_document(document_id)
    return {"message": f"Vectors for document '{doc.filename}' deleted successfully"}


@router.post("/reindex-all", summary="Admin Re-index All Documents")
def reindex_all(
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Clears vector store and re-indexes all completed documents. Restricted to ADMIN.
    """
    stats = reindex_all_documents(db)
    return {
        "message": "Vector store re-indexed successfully",
        "stats": stats
    }
