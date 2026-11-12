import logging
from functools import lru_cache

from sentence_transformers import CrossEncoder

from src.core.config import get_settings
from src.models.okf import RetrievedChunk

logger = logging.getLogger(__name__)


@lru_cache
def get_reranker() -> CrossEncoder:
    """Cached local cross-encoder (BAAI/bge-reranker-base, runs on CPU, no API calls)."""
    settings = get_settings()
    return CrossEncoder(settings.reranker_model, device=settings.embedding_device)


def rerank_chunks(query: str, chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
    """Score (query, chunk) pairs with the cross-encoder and return the top_k, sorted descending."""
    if not chunks:
        return []

    pairs = [(query, chunk.content) for chunk in chunks]
    scores = get_reranker().predict(pairs)

    for chunk, score in zip(chunks, scores, strict=True):
        chunk.rerank_score = float(score)

    chunks.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
    return chunks[:top_k]
