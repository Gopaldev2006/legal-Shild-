import numpy as np
from typing import List, Dict, Any, Optional, Callable
from app.services.vector.embedding_service import generate_embedding


class CaseVectorStore:
    """
    Vector Repository for Case Law Dataset.
    Indexes case embeddings and metadata for semantic similarity search.
    """

    def __init__(self):
        self.vectors: List[np.ndarray] = []
        self.metadata_store: List[Dict[str, Any]] = []

    def clear_all(self):
        """Clears all indexed case vectors."""
        self.vectors = []
        self.metadata_store = []

    def add_case_vector(self, vector: List[float], metadata: Dict[str, Any]):
        """Adds a case vector and metadata to the repository."""
        vec_np = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(vec_np)
        if norm > 0:
            vec_np = vec_np / norm

        self.vectors.append(vec_np)
        self.metadata_store.append(metadata)

    def search_cases(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes cosine similarity search over case vectors with metadata filtering.
        """
        if not self.vectors:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        matrix = np.vstack(self.vectors)
        similarities = np.dot(matrix, q_vec)

        results = []
        for idx, score in enumerate(similarities):
            meta = self.metadata_store[idx]
            if filter_fn and not filter_fn(meta):
                continue

            item = dict(meta)
            item["score"] = round(float(score), 4)
            results.append(item)

        # Sort descending by similarity score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


case_vector_repo = CaseVectorStore()
