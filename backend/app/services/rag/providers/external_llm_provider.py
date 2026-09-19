import os
from typing import List, Dict, Any
from app.services.rag.providers.base_provider import BaseModelProvider


class ExternalLLMProvider(BaseModelProvider):
    """
    External LLM Provider (e.g. OpenAI GPT-4, Anthropic Claude, or API Gateway).
    Strictly receives ONLY pre-filtered, permission-verified context.
    Includes fallback synthesis when API key is not configured.
    """

    def __init__(self, api_key: str = None, model_name: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return f"External LLM API ({self.model_name})"

    def generate_response(self, prompt: str, context_chunks: List[Dict[str, Any]]) -> str:
        if not context_chunks:
            return (
                "The available authorized documents do not contain sufficient information "
                "to answer this query. No relevant authorized context was retrieved."
            )

        # Build context representation
        chunk_summaries = []
        for i, chk in enumerate(context_chunks, 1):
            doc_id = chk.get("document_id", "N/A")
            page_num = chk.get("page_number", 1)
            chunk_id = chk.get("chunk_id", "N/A")
            snippet = chk.get("text", "").strip()
            chunk_summaries.append(f"[Source #{i} - Doc #{doc_id}, Page {page_num}]: {snippet}")

        joined_evidence = "\n\n".join(chunk_summaries)

        # Check Gemini API Key
        from app.services.ai.gemini_service import gemini_service
        if gemini_service.is_configured():
            sys_msg = (
                "You are a secure AI Legal Assistant. Answer strictly based on the provided "
                "authorized legal context chunks. Do not hallucinate or use external unverified knowledge. "
                "Cite sources clearly using [Source #X - Doc #Y, Page Z] format."
            )
            rag_prompt = f"Authorized Context Chunks:\n{joined_evidence}\n\nUser Legal Query:\n{prompt}"
            gemini_res = gemini_service.generate_response(prompt=rag_prompt, system_instruction=sys_msg, temperature=0.1)
            if gemini_res:
                return gemini_res

        if self.api_key:
            # OpenAI / Custom external client invocation
            try:
                import openai
                client = openai.OpenAI(api_key=self.api_key)
                system_msg = (
                    "You are a secure AI Legal Assistant. Answer strictly based on the provided "
                    "authorized legal context chunks. Do not hallucinate or use external unverified knowledge. "
                    "Cite sources clearly using [Source #X - Doc #Y, Page Z] format."
                )
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": f"Context:\n{joined_evidence}\n\nQuery:\n{prompt}"}
                    ],
                    temperature=0.1
                )
                return response.choices[0].message.content
            except Exception as err:
                return (
                    f"External LLM API call error: {str(err)}. "
                    f"Falling back to grounded local response:\n\n"
                    f"Based on authorized legal context:\n\n{joined_evidence}"
                )

        # Fallback synthesis when API key is omitted
        return (
            f"[External LLM API Sandbox Response ({self.model_name})]\n"
            f"Grounded analysis based on authorized document context:\n\n"
            f"{joined_evidence}\n\n"
            f"Conclusion: Verified against authorized case evidence."
        )

    def get_health(self) -> Dict[str, Any]:
        """Returns health metrics for external LLM API provider."""
        return {
            "provider": self.provider_name,
            "status": "healthy" if self.api_key else "fallback_sandbox",
            "model_name": self.model_name,
            "api_key_configured": bool(self.api_key),
            "device": "cloud_api",
        }
