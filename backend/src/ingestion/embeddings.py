import hashlib
import logging
from functools import lru_cache

from langchain_community.embeddings import HuggingFaceEmbeddings

from src.core.config import get_settings
from src.models.okf import KnowledgeChunk

logger = logging.getLogger(__name__)

SPARSE_VOCAB_SIZE = 2**18  # hashing-trick bucket count


@lru_cache
def get_embedding_model() -> HuggingFaceEmbeddings:
    """Cached local embedding model (BAAI/bge-small-en-v1.5, runs on CPU, no API calls)."""
    settings = get_settings()
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": True},
    )


def embed_dense_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with the local BGE model."""
    return get_embedding_model().embed_documents(texts)


def embed_query(text: str) -> list[float]:
    """Embed a single query string (uses BGE's query-specific prefix internally)."""
    return get_embedding_model().embed_query(text)


def compute_sparse_embedding(text: str) -> dict[int, float]:
    """Lightweight hashing-trick sparse vector (token -> term frequency).

    A free, fully local stand-in for a learned sparse model (BM25/SPLADE):
    it gives Qdrant hybrid search a usable sparse signal at zero extra model
    or API cost. Swap in a real sparse encoder later if rare-term recall
    needs to improve.
    """
    weights: dict[int, float] = {}
    for token in text.lower().split():
        index = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % SPARSE_VOCAB_SIZE
        weights[index] = weights.get(index, 0.0) + 1.0
    return weights


def embed_chunks(chunks: list[KnowledgeChunk], include_sparse: bool = True) -> list[KnowledgeChunk]:
    """Populate dense_embedding (and optionally sparse_embedding) on each chunk, in place."""
    if not chunks:
        return chunks

    dense_vectors = embed_dense_batch([chunk.content for chunk in chunks])
    for chunk, vector in zip(chunks, dense_vectors, strict=True):
        chunk.dense_embedding = vector
        if include_sparse:
            chunk.sparse_embedding = compute_sparse_embedding(chunk.content)

    logger.info("Embedded %d chunks%s", len(chunks), " (dense + sparse)" if include_sparse else " (dense only)")
    return chunks
