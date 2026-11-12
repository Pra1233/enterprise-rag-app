"""Retrieval-only evaluation: compares dense / sparse / hybrid / hybrid+rerank
against each case's expected_document_ids (and expected_chunk_ids, if given).

Reuses the exact production retrieval building blocks — src.ingestion.embeddings
for query embedding, src.retrieval.qdrant_client for search, src.retrieval.reranker
for reranking — and the same tenant-scoped authorization filter the API enforces.
No separate retrieval implementation is created for evaluation purposes.
"""

import logging
import time
from dataclasses import dataclass, field
from statistics import mean

from src.evaluation.dataset import EvaluationCase
from src.evaluation.metrics import (
    dedupe_preserve_order,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from src.ingestion.embeddings import compute_sparse_embedding, embed_query
from src.models.okf import RetrievedChunk
from src.retrieval.qdrant_client import build_tenant_filter, search_hybrid, search_similar, search_sparse
from src.retrieval.reranker import rerank_chunks

logger = logging.getLogger(__name__)

RETRIEVAL_STRATEGIES = ("dense", "sparse", "hybrid", "hybrid_rerank")


@dataclass
class StrategyResult:
    strategy: str
    retrieved_document_ids: list[str]
    retrieved_chunk_ids: list[str]
    latency_seconds: float
    # Document-level metrics (always computed when expected_document_ids is set).
    recall_at_k: float | None = None
    precision_at_k: float | None = None
    mrr: float | None = None
    hit_rate_at_k: float | None = None
    ndcg_at_k: float | None = None
    # Chunk-level metrics — only populated when the case provides expected_chunk_ids.
    chunk_recall_at_k: float | None = None
    chunk_precision_at_k: float | None = None


@dataclass
class RetrievalCaseResult:
    case_id: str
    question: str
    top_k: int
    strategies: dict[str, StrategyResult] = field(default_factory=dict)
    error: str | None = None


def _score_strategy(
    chunks: list[RetrievedChunk], case: EvaluationCase, top_k: int, strategy: str, latency: float
) -> StrategyResult:
    chunk_ids = [str(c.chunk_id) for c in chunks]
    document_ids = dedupe_preserve_order([str(c.document_id) for c in chunks])
    expected_docs = set(case.expected_document_ids)

    result = StrategyResult(
        strategy=strategy,
        retrieved_document_ids=document_ids,
        retrieved_chunk_ids=chunk_ids,
        latency_seconds=latency,
        recall_at_k=recall_at_k(document_ids, expected_docs, top_k),
        precision_at_k=precision_at_k(document_ids, expected_docs, top_k),
        mrr=mean_reciprocal_rank(document_ids, expected_docs),
        hit_rate_at_k=hit_rate_at_k(document_ids, expected_docs, top_k),
        ndcg_at_k=ndcg_at_k(document_ids, expected_docs, top_k),
    )

    if case.expected_chunk_ids:
        expected_chunks = set(case.expected_chunk_ids)
        result.chunk_recall_at_k = recall_at_k(chunk_ids, expected_chunks, top_k)
        result.chunk_precision_at_k = precision_at_k(chunk_ids, expected_chunks, top_k)

    return result


def evaluate_retrieval_case(
    case: EvaluationCase,
    tenant_id: str,
    top_k: int = 5,
    rerank_top_k: int = 5,
    strategies: tuple[str, ...] = RETRIEVAL_STRATEGIES,
) -> RetrievalCaseResult:
    """Run every requested retrieval strategy for one question and score each."""
    query_filter = build_tenant_filter(tenant_id, document_type=case.metadata.get("document_type"))
    result = RetrievalCaseResult(case_id=case.case_id, question=case.question, top_k=top_k)

    try:
        dense_vector = embed_query(case.question)
        sparse_vector = compute_sparse_embedding(case.question)
        hybrid_chunks: list[RetrievedChunk] = []

        if "dense" in strategies:
            start = time.monotonic()
            dense_chunks = search_similar(dense_vector, limit=top_k, query_filter=query_filter)
            result.strategies["dense"] = _score_strategy(dense_chunks, case, top_k, "dense", time.monotonic() - start)

        if "sparse" in strategies:
            start = time.monotonic()
            sparse_chunks = search_sparse(sparse_vector, limit=top_k, query_filter=query_filter)
            result.strategies["sparse"] = _score_strategy(
                sparse_chunks, case, top_k, "sparse", time.monotonic() - start
            )

        if "hybrid" in strategies or "hybrid_rerank" in strategies:
            start = time.monotonic()
            hybrid_chunks = search_hybrid(dense_vector, sparse_vector, limit=top_k, query_filter=query_filter)
            hybrid_latency = time.monotonic() - start
            if "hybrid" in strategies:
                result.strategies["hybrid"] = _score_strategy(hybrid_chunks, case, top_k, "hybrid", hybrid_latency)

        if "hybrid_rerank" in strategies:
            start = time.monotonic()
            reranked = rerank_chunks(case.question, list(hybrid_chunks), top_k=rerank_top_k)
            rerank_latency = time.monotonic() - start
            result.strategies["hybrid_rerank"] = _score_strategy(
                reranked, case, rerank_top_k, "hybrid_rerank", hybrid_latency + rerank_latency
            )

    except Exception as exc:
        logger.error("Retrieval evaluation failed for case '%s'", case.case_id, exc_info=True)
        result.error = str(exc)

    return result


_METRIC_FIELDS = ("recall_at_k", "precision_at_k", "mrr", "hit_rate_at_k", "ndcg_at_k")


def summarize_retrieval_results(case_results: list[RetrievalCaseResult]) -> dict[str, dict[str, float | None]]:
    """Mean of each metric per strategy, across every case that didn't error.

    This is the basis for the "does hybrid/reranking actually help" comparison
    — it makes no assumption about which strategy wins.
    """
    summary: dict[str, dict[str, float | None]] = {}

    strategies: set[str] = set()
    for case_result in case_results:
        if case_result.error is None:
            strategies.update(case_result.strategies.keys())

    for strategy in strategies:
        per_metric: dict[str, float | None] = {}
        for metric_name in _METRIC_FIELDS:
            values = []
            for cr in case_results:
                if cr.error is not None or strategy not in cr.strategies:
                    continue
                value = getattr(cr.strategies[strategy], metric_name)
                if value is not None:
                    values.append(value)
            per_metric[metric_name] = mean(values) if values else None

        latencies = [
            cr.strategies[strategy].latency_seconds
            for cr in case_results
            if cr.error is None and strategy in cr.strategies
        ]
        per_metric["mean_latency_seconds"] = mean(latencies) if latencies else None
        summary[strategy] = per_metric

    return summary
