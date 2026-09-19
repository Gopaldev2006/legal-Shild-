from typing import List, Dict, Any
from app.services.rag.providers.base_provider import BaseModelProvider


class MockSLMProvider(BaseModelProvider):
    """
    Mock SLM Provider for Unit & Integration Testing.
    Executes instant, deterministic grounded inference without requiring network model weights downloads.
    """

    def __init__(
        self,
        model_name: str = "mock-slm-legal-v1",
        max_new_tokens: int = 512,
        temperature: float = 0.1,
        device: str = "cpu",
        simulated_error: bool = False
    ):
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.device = device
        self.simulated_error = simulated_error

    @property
    def provider_name(self) -> str:
        return f"Mock SLM Provider ({self.model_name} on {self.device})"

    def generate_response(self, prompt: str, context_chunks: List[Dict[str, Any]]) -> str:
        if self.simulated_error:
            raise RuntimeError("Simulated SLM inference hardware error")

        if not context_chunks:
            return (
                "The available authorized documents do not contain sufficient information "
                "to answer this query. No relevant authorized context was retrieved."
            )

        chunk_summaries = []
        for i, chk in enumerate(context_chunks, 1):
            doc_id = chk.get("document_id", "N/A")
            page_num = chk.get("page_number", 1)
            snippet = chk.get("text", "").strip()
            chunk_summaries.append(f"[Source #{i} - Doc #{doc_id}, Page {page_num}]: {snippet}")

        joined_evidence = "\n\n".join(chunk_summaries)

        return (
            f"[Mock SLM Analysis Output ({self.model_name})]\n"
            f"Based on authorized legal context:\n\n{joined_evidence}\n\n"
            f"Grounding Status: Verified against authorized user files."
        )

    def get_health(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": "healthy",
            "model_name": self.model_name,
            "requested_device": self.device,
            "active_device": self.device,
            "generation_parameters": {
                "max_new_tokens": self.max_new_tokens,
                "temperature": self.temperature,
            },
            "memory_usage": {
                "ram_usage_mb": 12.5,
                "gpu_memory_allocated_mb": "N/A"
            },
            "load_error": None
        }
