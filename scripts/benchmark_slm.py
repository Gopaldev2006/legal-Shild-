import time
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.services.rag.providers.local_slm_provider import LocalSLMProvider
from app.services.rag.providers.mock_provider import MockSLMProvider


def run_slm_benchmark():
    print("=" * 60)
    print(" SMALL LANGUAGE MODEL (SLM) BENCHMARK SUITE")
    print("=" * 60)

    # 1. Inspect configuration
    print(f"Configured MODEL_NAME:     {settings.MODEL_NAME}")
    print(f"Configured MAX_NEW_TOKENS: {settings.MAX_NEW_TOKENS}")
    print(f"Configured TEMPERATURE:    {settings.TEMPERATURE}")
    print(f"Configured DEVICE:         {settings.DEVICE}")
    print("-" * 60)

    # 2. Benchmark LocalSLMProvider
    provider = LocalSLMProvider()
    health = provider.get_health()

    print(f"Active Provider Name:     {provider.provider_name}")
    print(f"Active Device Placement:  {health['active_device']}")
    print(f"Model Load Status:        {health['status']}")
    print(f"RAM Memory Usage:         {health['memory_usage']['ram_usage_mb']} MB")
    print(f"GPU Memory Allocated:     {health['memory_usage']['gpu_memory_allocated_mb']}")
    print("-" * 60)

    # Benchmark Prompt & Context
    benchmark_prompt = "Analyze the legal liability under Section 302 IPC and contract indemnity requirements."
    benchmark_chunks = [
        {
            "document_id": 101,
            "page_number": 2,
            "chunk_id": "chk_bench_1",
            "text": "The indemnity clause under Section 14 requires Tenant to pay 5000 USD for property damage."
        },
        {
            "document_id": 102,
            "page_number": 5,
            "chunk_id": "chk_bench_2",
            "text": "Section 302 of the Indian Penal Code mandates life imprisonment or death penalty for culpable homicide."
        }
    ]

    print("Running Inference Benchmark (Warm-up + 3 Iterations)...")
    latencies = []

    # Warm-up run
    _ = provider.generate_response(benchmark_prompt, benchmark_chunks)

    for i in range(1, 4):
        start_t = time.time()
        response = provider.generate_response(benchmark_prompt, benchmark_chunks)
        latency = time.time() - start_t
        latencies.append(latency)
        char_count = len(response)
        word_count = len(response.split())
        print(f"Iteration #{i}: Latency = {latency:.4f}s | Output Chars = {char_count} | Output Words = {word_count}")

    avg_latency = sum(latencies) / len(latencies)
    print("-" * 60)
    print(f"AVERAGE BENCHMARK LATENCY:  {avg_latency:.4f} seconds")
    print(f"BENCHMARK COMPLETED SUCCESSFULLY [OK]")
    print("=" * 60)


if __name__ == "__main__":
    run_slm_benchmark()
