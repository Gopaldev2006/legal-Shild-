import os
import json
import logging
from typing import List, Dict, Any, Optional, Callable
import numpy as np

logger = logging.getLogger(__name__)

VECTOR_STORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "vector_store"))
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
INDEX_FILE = os.path.join(VECTOR_STORE_DIR, "legal_faiss.index")
METADATA_FILE = os.path.join(VECTOR_STORE_DIR, "vector_metadata.json")


class VectorRepository:
    """
    Isolated Vector Database Manager.
    Manages vector embeddings and metadata records with FAISS / NumPy cosine similarity.
    Every record retains document_id, owner_id, matter_id, chunk_id, source_type, page_number, document_type, and text.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.metadata_store: List[Dict[str, Any]] = []  # List of metadata dicts corresponding to vectors
        self.vectors: Optional[np.ndarray] = None        # 2D Float32 numpy array of normalized vectors
        self._load_store()

    def _load_store(self):
        """Loads persisted vectors and metadata from data/vector_store/ if present."""
        if os.path.exists(METADATA_FILE):
            try:
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    self.metadata_store = json.load(f)
            except Exception as e:
                logger.error(f"Error loading vector metadata: {e}")
                self.metadata_store = []

        if os.path.exists(INDEX_FILE):
            try:
                self.vectors = np.load(INDEX_FILE)
            except Exception as e:
                logger.error(f"Error loading vector index array: {e}")
                self.vectors = None

    def _save_store(self):
        """Persists vectors and metadata to disk."""
        try:
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.metadata_store, f, indent=2)
            if self.vectors is not None:
                np.save(INDEX_FILE, self.vectors)
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")

    def add_vectors(self, records: List[Dict[str, Any]]):
        """
        Adds vector records to the repository.
        Each record must contain 'vector' (List[float]) and metadata fields.
        """
        if not records:
            return

        new_vecs = []
        for rec in records:
            vec = np.array(rec["vector"], dtype=np.float32)
            # Normalize vector to unit length for Cosine Similarity
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            new_vecs.append(vec)

            meta = {
                "chunk_id": rec["chunk_id"],
                "document_id": int(rec["document_id"]),
                "owner_id": int(rec["owner_id"]),
                "matter_id": rec.get("matter_id"),
                "source_type": rec.get("source_type", "txt"),
                "page_number": rec.get("page_number"),
                "document_type": rec.get("document_type", "general"),
                "text": rec["text"]
            }
            self.metadata_store.append(meta)

        new_matrix = np.vstack(new_vecs)
        if self.vectors is None or len(self.vectors) == 0:
            self.vectors = new_matrix
        else:
            self.vectors = np.vstack([self.vectors, new_matrix])

        self._save_store()

    def search_vectors(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches vectors using Cosine Similarity (Inner Product of normalized vectors).
        Applies strict metadata authorization filter DURING retrieval before returning results.
        """
        if self.vectors is None or len(self.vectors) == 0 or not self.metadata_store:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        # Compute Cosine Similarity scores against all vectors
        scores = np.dot(self.vectors, q_vec)

        # Sort indices by score descending
        sorted_indices = np.argsort(-scores)

        results = []
        for idx in sorted_indices:
            score = float(scores[idx])
            meta = self.metadata_store[idx]

            # Apply metadata filter DURING retrieval (Security check)
            if filter_fn is not None and not filter_fn(meta):
                continue

            item = dict(meta)
            item["score"] = round(score, 4)
            results.append(item)

            if len(results) >= top_k:
                break

        return results

    def delete_by_document(self, document_id: int):
        """Removes all vectors and metadata matching document_id."""
        if self.vectors is None or not self.metadata_store:
            return

        keep_indices = []
        new_metadata = []

        for idx, meta in enumerate(self.metadata_store):
            if int(meta["document_id"]) != int(document_id):
                keep_indices.append(idx)
                new_metadata.append(meta)

        if len(keep_indices) == len(self.metadata_store):
            return  # No vectors matched

        if len(keep_indices) == 0:
            self.vectors = None
            self.metadata_store = []
        else:
            self.vectors = self.vectors[keep_indices]
            self.metadata_store = new_metadata

        self._save_store()

    def clear_all(self):
        """Clears all vectors and metadata."""
        self.vectors = None
        self.metadata_store = []
        self._save_store()


# Global vector repository singleton instance
vector_repo = VectorRepository()
