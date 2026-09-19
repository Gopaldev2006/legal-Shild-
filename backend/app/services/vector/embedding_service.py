import logging
from typing import List
import numpy as np

logger = logging.getLogger(__name__)

_model_instance = None
EMBEDDING_DIM = 384


def _get_model():
    global _model_instance
    if _model_instance is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Load lightweight 384-dim SentenceTransformer model for English legal semantic search
            _model_instance = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load SentenceTransformer model ({e}). Using normalized dense vector fallback.")
            _model_instance = "FALLBACK"
    return _model_instance


def _fallback_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Deterministically maps text content to a normalized dense vector of dimension `dim`."""
    if not text:
        vec = np.zeros(dim, dtype=np.float32)
    else:
        # Seed pseudo-random generator with hash of text for deterministic reproducible vector
        seed = abs(hash(text)) % (2**32)
        rng = np.random.RandomState(seed)
        vec = rng.randn(dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
    return vec.tolist()


def generate_embedding(text: str) -> List[float]:
    """Generates a dense vector embedding (384 dimensions) for input text."""
    model = _get_model()
    if model == "FALLBACK" or model is None:
        return _fallback_embedding(text)

    try:
        embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        return _fallback_embedding(text)


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generates dense vector embeddings for a list of text strings."""
    if not texts:
        return []
    model = _get_model()
    if model == "FALLBACK" or model is None:
        return [_fallback_embedding(t) for t in texts]

    try:
        embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.error(f"Batch embedding generation error: {e}")
        return [_fallback_embedding(t) for t in texts]
