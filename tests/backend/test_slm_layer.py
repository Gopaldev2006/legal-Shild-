import pytest
from app.core.config import settings
from app.services.rag.providers.base_provider import BaseModelProvider
from app.services.rag.providers.local_slm_provider import LocalSLMProvider
from app.services.rag.providers.mock_provider import MockSLMProvider


def test_slm_settings_configuration():
    assert hasattr(settings, "MODEL_NAME")
    assert hasattr(settings, "MAX_NEW_TOKENS")
    assert hasattr(settings, "TEMPERATURE")
    assert hasattr(settings, "DEVICE")
    assert isinstance(settings.MAX_NEW_TOKENS, int)
    assert isinstance(settings.TEMPERATURE, float)


def test_gpu_cpu_fallback_logic():
    # Force request CUDA device
    provider = LocalSLMProvider(device="cuda")
    # Verify active device is resolved (either cuda or cpu fallback)
    assert "cpu" in provider.active_device or "cuda" in provider.active_device


def test_model_health_check():
    mock_p = MockSLMProvider(model_name="test-legal-slm", max_new_tokens=256, temperature=0.2, device="cpu")
    health = mock_p.get_health()

    assert health["provider"] == "Mock SLM Provider (test-legal-slm on cpu)"
    assert health["status"] == "healthy"
    assert health["model_name"] == "test-legal-slm"
    assert health["requested_device"] == "cpu"
    assert health["generation_parameters"]["max_new_tokens"] == 256
    assert health["generation_parameters"]["temperature"] == 0.2
    assert "ram_usage_mb" in health["memory_usage"]


def test_mock_provider_inference():
    provider = MockSLMProvider(model_name="mock-slm")
    prompt = "What is the penalty under Section 302?"
    chunks = [
        {"document_id": 1, "page_number": 3, "text": "Section 302 IPC mandates death penalty or life imprisonment."}
    ]

    response = provider.generate_response(prompt, chunks)
    assert "[Mock SLM Analysis Output (mock-slm)]" in response
    assert "Section 302 IPC" in response
    assert "Doc #1" in response


def test_authorized_context_security():
    provider = MockSLMProvider()
    prompt = "What is the secret formula?"
    empty_chunks = []

    # Model MUST refuse when context is empty
    response = provider.generate_response(prompt, empty_chunks)
    assert "do not contain sufficient information" in response


def test_error_and_timeout_handling():
    error_provider = MockSLMProvider(simulated_error=True)
    chunks = [{"document_id": 1, "text": "Some text"}]

    with pytest.raises(RuntimeError) as exc_info:
        error_provider.generate_response("Test query", chunks)

    assert "Simulated SLM inference hardware error" in str(exc_info.value)
