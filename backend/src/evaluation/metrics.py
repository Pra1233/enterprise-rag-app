"""Evaluation metrics: standard information-retrieval metrics (pure functions,
no RAGAS dependency) plus RAGAS answer/context quality metrics wired to the
application's EXISTING Groq LLM and HuggingFace embeddings — never a second,
separately-configured model.

IR metrics all return `None` (not 0.0) when their required ground truth is
missing, per the instruction not to compute a metric without the data it needs.
"""

import logging
import math
from functools import lru_cache

from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

from src.ingestion.embeddings import get_embedding_model
from src.retrieval.graph import get_llm

logger = logging.getLogger(__name__)


# --- Information retrieval metrics (document-level OR chunk-level — caller decides which IDs to pass) ---


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    """Fraction of relevant items that appear in the top-K retrieved."""
    if not relevant_ids:
        return None
    hits = len(set(retrieved_ids[:k]) & relevant_ids)
    return hits / len(relevant_ids)


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    """Fraction of the top-K retrieved items that are relevant.

    Divides by min(k, len(retrieved)) rather than a fixed k, so a pipeline
    that legitimately returns fewer than K candidates isn't penalized for it.
    """
    if not relevant_ids:
        return None
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = len(set(top_k) & relevant_ids)
    return hits / len(top_k)


def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float | None:
    """1 / rank of the first relevant item found (1-indexed); 0.0 if none found."""
    if not relevant_ids:
        return None
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def hit_rate_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    """1.0 if any relevant item appears in the top-K, else 0.0."""
    if not relevant_ids:
        return None
    return 1.0 if set(retrieved_ids[:k]) & relevant_ids else 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    """Normalized Discounted Cumulative Gain @ K, with binary relevance
    (1 if the retrieved item is in relevant_ids, else 0).
    """
    if not relevant_ids:
        return None

    top_k = retrieved_ids[:k]
    dcg = sum((1.0 if doc_id in relevant_ids else 0.0) / math.log2(i + 2) for i, doc_id in enumerate(top_k))

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    return dcg / idcg if idcg > 0 else 0.0


def dedupe_preserve_order(ids: list[str]) -> list[str]:
    """Collapse a ranked list to first-occurrence order — used to turn a
    chunk-level ranking into a document-level ranking without losing rank info.
    """
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# --- RAGAS metrics, wired to the application's existing models ---


@lru_cache
def _wrapped_llm() -> LangchainLLMWrapper:
    return LangchainLLMWrapper(get_llm())


@lru_cache
def _wrapped_embeddings() -> LangchainEmbeddingsWrapper:
    return LangchainEmbeddingsWrapper(get_embedding_model())


@lru_cache
def get_ragas_metrics() -> dict[str, object]:
    """Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall — all
    using the app's existing ChatGroq + HuggingFaceEmbeddings, not a second
    model configuration.
    """
    llm = _wrapped_llm()
    embeddings = _wrapped_embeddings()
    return {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": ContextPrecision(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }


async def score_single_turn(sample, metric_names: list[str] | None = None) -> dict[str, float | None]:
    """Score one SingleTurnSample against the named RAGAS metrics (default: all).

    A metric that fails (e.g. a transient Groq error) is recorded as None with
    the failure logged, rather than aborting the whole case's evaluation.
    """
    metrics = get_ragas_metrics()
    names = metric_names or list(metrics.keys())

    scores: dict[str, float | None] = {}
    for name in names:
        metric = metrics[name]
        try:
            scores[name] = await metric.single_turn_ascore(sample)
        except Exception:
            logger.error("RAGAS metric '%s' failed for this sample", name, exc_info=True)
            scores[name] = None
    return scores
