"""
System Performance Benchmark Engine for Phase 15.

Measures RAG query screening latency, vector retrieval speed, SLM inference time,
RAM memory utilization, and active system health metrics.
"""

import time
import os
import psutil
from typing import Dict, Any, Optional
from app.services.vector.retrieval_service import retrieval_service, UserContext
from app.services.rag.query_processor import QueryProcessor
from app.services.rag.prompt_builder import PromptBuilder
from app.services.rag.providers.local_slm_provider import LocalSLMProvider


class SystemBenchmarkEngine:
    """
    Measures component-level latency and system resource utilization.
    """

    def __init__(self):
        self.query_processor = QueryProcessor()
        self.prompt_builder = PromptBuilder()
        self.local_provider = LocalSLMProvider()

    def get_memory_usage_mb(self) -> float:
        """Return current process RAM usage in Megabytes."""
        try:
            process = psutil.Process(os.getpid())
            return round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return 45.0  # Fallback estimate in MB

    def benchmark_rag_performance(
        self, query_text: str, user_context: UserContext, top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Executes a benchmark run measuring query screening, vector search,
        prompt assembly, and SLM response generation latency.
        """
        start_total = time.perf_counter()
        initial_ram = self.get_memory_usage_mb()

        # Step 1: Query Screening Benchmark
        t0 = time.perf_counter()
        screen_res = self.query_processor.screen_query(query_text)
        screening_latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Step 2: Vector Retrieval Benchmark
        t1 = time.perf_counter()
        retrieved_chunks = retrieval_service.search(
            query=screen_res["sanitized_query"],
            user_context=user_context,
            top_k=top_k
        )
        retrieval_latency_ms = round((time.perf_counter() - t1) * 1000, 2)

        # Step 3: Prompt Construction Benchmark
        t2 = time.perf_counter()
        prompt_data = self.prompt_builder.build_prompt(
            sanitized_query=screen_res["sanitized_query"],
            context_chunks=retrieved_chunks
        )
        prompt_build_latency_ms = round((time.perf_counter() - t2) * 1000, 2)

        # Step 4: SLM Generation Benchmark
        t3 = time.perf_counter()
        raw_response = self.local_provider.generate_response(
            prompt=prompt_data["prompt"],
            context_chunks=retrieved_chunks
        )
        generation_latency_seconds = round(time.perf_counter() - t3, 3)

        total_latency_seconds = round(time.perf_counter() - start_total, 3)
        final_ram = self.get_memory_usage_mb()

        return {
            "status": "COMPLETED",
            "query_text": query_text,
            "chunks_retrieved": len(retrieved_chunks),
            "performance_metrics": {
                "screening_latency_ms": screening_latency_ms,
                "retrieval_latency_ms": retrieval_latency_ms,
                "prompt_build_latency_ms": prompt_build_latency_ms,
                "slm_generation_latency_seconds": generation_latency_seconds,
                "total_end_to_end_latency_seconds": total_latency_seconds,
                "initial_memory_mb": initial_ram,
                "final_memory_mb": final_ram,
                "memory_delta_mb": round(final_ram - initial_ram, 2),
            },
            "system_status": {
                "memory_healthy": final_ram < 2048.0,
                "retrieval_speed_healthy": retrieval_latency_ms < 500.0,
            }
        }


benchmark_engine = SystemBenchmarkEngine()
