"""In-process performance/reliability metrics collection.

Deliberately lightweight — an in-memory registry, no new infrastructure
dependency. The counters are grouped so they can be re-exported to
Prometheus/StatsD/CloudWatch later without changing any call site.
"""

import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Histogram:
    values: list[float] = field(default_factory=list)

    def record(self, value: float) -> None:
        self.values.append(value)

    def mean(self) -> float | None:
        return sum(self.values) / len(self.values) if self.values else None

    def p95(self) -> float | None:
        if not self.values:
            return None
        ordered = sorted(self.values)
        index = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
        return ordered[index]


class MetricsRegistry:
    """Process-wide metrics collector. Use get_metrics_registry() for the shared instance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # API metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self._response_times = _Histogram()

        # RAG stage metrics (query preprocessing, embedding, retrieval, reranking, generation, total)
        self._stage_latencies: dict[str, _Histogram] = defaultdict(_Histogram)

        # Ingestion metrics
        self.documents_processed = 0
        self.ingestion_successes = 0
        self.ingestion_failures = 0
        self._ingestion_durations = _Histogram()
        self._chunks_per_document = _Histogram()

        # LLM metrics
        self._llm_input_tokens = _Histogram()
        self._llm_output_tokens = _Histogram()
        self._llm_latencies: dict[str, _Histogram] = defaultdict(_Histogram)
        self.rate_limit_errors = 0

    # --- API ---

    def record_request(self, duration_seconds: float, success: bool) -> None:
        with self._lock:
            self.total_requests += 1
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
            self._response_times.record(duration_seconds)

    # --- RAG pipeline stages ---

    def record_stage_latency(self, stage: str, duration_seconds: float) -> None:
        with self._lock:
            self._stage_latencies[stage].record(duration_seconds)

    @contextmanager
    def time_stage(self, stage: str):
        """Context manager: `with registry.time_stage('retrieval'): ...`"""
        start = time.monotonic()
        try:
            yield
        finally:
            self.record_stage_latency(stage, time.monotonic() - start)

    # --- Ingestion ---

    def record_ingestion(self, success: bool, duration_seconds: float, chunk_count: int | None = None) -> None:
        with self._lock:
            self.documents_processed += 1
            if success:
                self.ingestion_successes += 1
            else:
                self.ingestion_failures += 1
            self._ingestion_durations.record(duration_seconds)
            if chunk_count is not None:
                self._chunks_per_document.record(chunk_count)

    # --- LLM ---

    def record_llm_usage(
        self,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
        latency_seconds: float,
        rate_limited: bool = False,
    ) -> None:
        """Record LLM call stats. Pass provider-reported token counts (or None
        if unavailable) — never a character-count estimate.
        """
        with self._lock:
            if input_tokens is not None:
                self._llm_input_tokens.record(input_tokens)
            if output_tokens is not None:
                self._llm_output_tokens.record(output_tokens)
            self._llm_latencies[model].record(latency_seconds)
            if rate_limited:
                self.rate_limit_errors += 1

    def snapshot(self) -> dict[str, Any]:
        """A point-in-time dict of every metric — safe to serialize to JSON."""
        with self._lock:
            return {
                "api": {
                    "total_requests": self.total_requests,
                    "successful_requests": self.successful_requests,
                    "failed_requests": self.failed_requests,
                    "avg_response_time_seconds": self._response_times.mean(),
                    "p95_response_time_seconds": self._response_times.p95(),
                },
                "rag_stages": {
                    stage: {"mean_seconds": hist.mean(), "p95_seconds": hist.p95()}
                    for stage, hist in self._stage_latencies.items()
                },
                "ingestion": {
                    "total_documents_processed": self.documents_processed,
                    "successful": self.ingestion_successes,
                    "failed": self.ingestion_failures,
                    "avg_processing_time_seconds": self._ingestion_durations.mean(),
                    "avg_chunks_per_document": self._chunks_per_document.mean(),
                },
                "llm": {
                    "avg_input_tokens": self._llm_input_tokens.mean(),
                    "avg_output_tokens": self._llm_output_tokens.mean(),
                    "rate_limit_errors": self.rate_limit_errors,
                    "latency_by_model_seconds": {
                        model: {"mean": hist.mean(), "p95": hist.p95()} for model, hist in self._llm_latencies.items()
                    },
                },
            }


_registry = MetricsRegistry()


def get_metrics_registry() -> MetricsRegistry:
    return _registry


def extract_token_usage(ai_message: Any) -> tuple[int | None, int | None, int | None]:
    """Pull (input_tokens, output_tokens, total_tokens) from a LangChain
    AIMessage's `usage_metadata`, when the provider reported it.

    Returns (None, None, None) rather than estimating from character/word
    counts when usage wasn't reported — per the instruction not to estimate
    exact token consumption.
    """
    usage = getattr(ai_message, "usage_metadata", None)
    if not usage:
        return None, None, None
    return usage.get("input_tokens"), usage.get("output_tokens"), usage.get("total_tokens")
