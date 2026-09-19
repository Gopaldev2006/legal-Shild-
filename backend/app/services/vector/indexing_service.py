import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.document import LegalDocument, DocumentChunk
from app.services.vector.embedding_service import generate_embeddings_batch
from app.services.vector.vector_repository import vector_repo

logger = logging.getLogger(__name__)


def index_document_chunks(db: Session, document_id: int) -> int:
    """
    Fetches DocumentChunks for document_id from SQL DB, generates vector embeddings,
    and inserts them into the vector repository with authorization metadata.
    Returns the count of indexed chunks.
    """
    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not doc:
        raise ValueError(f"Document #{document_id} not found")

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )

    if not chunks:
        logger.info(f"No chunks found for document #{document_id}")
        return 0

    # 1. Extract chunk text list
    texts = [chk.text for chk in chunks]

    # 2. Batch generate vector embeddings
    vectors = generate_embeddings_batch(texts)

    # 3. First remove existing vectors for this document to prevent duplicate indexing
    vector_repo.delete_by_document(document_id)

    # 4. Prepare vector records with full authorization metadata
    records = []
    for chk, vec in zip(chunks, vectors):
        records.append({
            "vector": vec,
            "chunk_id": chk.chunk_id,
            "document_id": doc.id,
            "owner_id": doc.owner_id,
            "matter_id": doc.matter_id,
            "source_type": doc.file_type,
            "page_number": chk.page_number,
            "document_type": doc.document_type.value,
            "text": chk.text
        })

    # 5. Insert vectors into vector repository
    vector_repo.add_vectors(records)
    logger.info(f"Successfully indexed {len(records)} chunks for document #{document_id}")
    return len(records)


def reindex_all_documents(db: Session) -> Dict[str, int]:
    """
    Admin utility: Clears vector store and re-indexes all COMPLETED documents from DB.
    """
    vector_repo.clear_all()
    
    docs = db.query(LegalDocument).all()
    total_docs = len(docs)
    total_chunks = 0

    for doc in docs:
        if doc.processing_status.value == "COMPLETED":
            count = index_document_chunks(db, doc.id)
            total_chunks += count

    return {
        "indexed_documents": total_docs,
        "indexed_chunks": total_chunks
    }
