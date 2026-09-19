"""
EmbeddingService
================
Singleton wrapper around sentence-transformers all-MiniLM-L6-v2.

Design decisions
----------------
* Model is loaded ONCE at first use (lazy init) and reused for the
  lifetime of the process — never re-initialized per chunk or request.
* Embeddings are float32 numpy arrays of dimension 384.
* Storage format: base64-encoded raw IEEE-754 float32 bytes.
  Decode with:
      import base64, numpy as np
      vec = np.frombuffer(base64.b64decode(stored_str), dtype=np.float32)
* Preprocessing: strip + lower before embedding (consistent for docs and
  queries so cosine similarity is meaningful).
* Batch size: 32 chunks per model call (good balance for CPU inference).
* Empty / whitespace-only texts are skipped — callers get None back.
"""

import base64
import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────
MODEL_NAME      = "all-MiniLM-L6-v2"
EMBEDDING_DIM   = 384          # all-MiniLM-L6-v2 output dimension
BATCH_SIZE      = 32           # chunks per model.encode() call


def _preprocess(text: str) -> str:
    """Consistent preprocessing for both documents and queries."""
    return text.strip()


def _to_storage(vec: np.ndarray) -> str:
    """Encode float32 numpy vector → base64 string for TEXT column."""
    return base64.b64encode(vec.astype(np.float32).tobytes()).decode("ascii")


def _from_storage(stored: str) -> np.ndarray:
    """Decode base64 string → float32 numpy vector."""
    return np.frombuffer(base64.b64decode(stored), dtype=np.float32)


# ── singleton ─────────────────────────────────────────────────────────────────

class EmbeddingService:
    """
    Lazy-loaded singleton.  Call EmbeddingService.get() to obtain the instance.
    The sentence-transformer model is loaded once on first use.
    """

    _instance: Optional["EmbeddingService"] = None
    _model = None          # SentenceTransformer instance

    def __init__(self):
        raise RuntimeError("Use EmbeddingService.get() — do not instantiate directly.")

    @classmethod
    def get(cls) -> "EmbeddingService":
        """Return the singleton instance, loading the model if needed."""
        if cls._instance is None:
            obj = object.__new__(cls)
            obj._load_model()
            cls._instance = obj
        return cls._instance

    def _load_model(self) -> None:
        """Load the sentence-transformer model (called once)."""
        logger.info("Loading embedding model: %s", MODEL_NAME)
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME)
            logger.info(
                "Embedding model loaded. Dimension: %d", EMBEDDING_DIM
            )
        except Exception as exc:
            logger.error("Failed to load embedding model: %s", exc)
            raise RuntimeError(f"EmbeddingService init failed: {type(exc).__name__}") from exc

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """
        Embed a single text string.
        Returns float32 numpy array of shape (384,) or None if text is empty.
        Preprocessing is applied before embedding (same as embed_batch).
        """
        clean = _preprocess(text)
        if not clean:
            return None
        vecs = self._model.encode([clean], normalize_embeddings=True, show_progress_bar=False)
        return vecs[0].astype(np.float32)

    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """
        Embed a list of texts in batches of BATCH_SIZE.
        Returns a list of the same length:
          - float32 ndarray for non-empty texts
          - None for empty / whitespace-only texts

        The same preprocessing used in embed_text is applied here so
        document and query embeddings are in the same vector space.
        """
        results: List[Optional[np.ndarray]] = []
        valid_indices: List[int]  = []
        valid_texts:   List[str]  = []

        for i, t in enumerate(texts):
            clean = _preprocess(t)
            if clean:
                valid_indices.append(i)
                valid_texts.append(clean)
            else:
                results.append(None)

        if not valid_texts:
            return results   # all empty

        # Pre-fill results with None placeholders for valid positions
        results_map: dict = {}
        for batch_start in range(0, len(valid_texts), BATCH_SIZE):
            batch = valid_texts[batch_start: batch_start + BATCH_SIZE]
            vecs  = self._model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=BATCH_SIZE,
            )
            for j, vec in enumerate(vecs):
                original_idx = valid_indices[batch_start + j]
                results_map[original_idx] = vec.astype(np.float32)

        # Merge back in original order
        final: List[Optional[np.ndarray]] = []
        valid_ptr = 0
        for i in range(len(texts)):
            if i in results_map:
                final.append(results_map[i])
            else:
                final.append(None)
        return final

    # ── validation ────────────────────────────────────────────────────────────

    def validate_embedding(self, vec: np.ndarray) -> bool:
        """
        Validate a single embedding vector:
        - must be a numpy array
        - must be float32
        - dimension must match EMBEDDING_DIM
        - must contain no NaN or Inf
        """
        if vec is None:
            return False
        if not isinstance(vec, np.ndarray):
            return False
        if vec.dtype != np.float32:
            return False
        if vec.shape != (EMBEDDING_DIM,):
            return False
        if not np.isfinite(vec).all():
            return False
        return True

    # ── storage helpers ───────────────────────────────────────────────────────

    @staticmethod
    def to_storage(vec: np.ndarray) -> str:
        """Encode embedding for TEXT column storage."""
        return _to_storage(vec)

    @staticmethod
    def from_storage(stored: str) -> np.ndarray:
        """Decode stored TEXT column back to float32 numpy vector."""
        return _from_storage(stored)
