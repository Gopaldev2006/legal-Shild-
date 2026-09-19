from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseModelProvider(ABC):
    """
    Abstract AI Model Provider Interface.
    Decouples RAG business logic from specific AI models (Local SLM vs External LLM).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns provider identification name."""
        pass

    @abstractmethod
    def generate_response(self, prompt: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        Generates AI response given a grounded RAG prompt and retrieved authorized context chunks.
        """
        pass

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """
        Returns model provider health check metrics, device placement, load status, and memory stats.
        """
        pass
