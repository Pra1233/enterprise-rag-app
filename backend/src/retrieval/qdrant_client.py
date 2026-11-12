import logging
from functools import lru_cache
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from src.core.config import get_settings
from src.models.okf import DocumentType, KnowledgeChunk, RetrievedChunk

logger = logging.getLogger(__name__)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DENSE_VECTOR_SIZE = 384  # BAAI/bge-small-en-v1.5 output dimension
UPSERT_BATCH_SIZE = 100

# Payload fields indexed for fast equality/filtering at query time.
# tenant_id is the authorization boundary: every search MUST filter on it.
FILTERABLE_PAYLOAD_FIELDS = ("tenant_id", "document_id", "document_type", "author")


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """Cached, process-wide Qdrant client."""
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def setup_collection() -> None:
    """Initialize the Qdrant collection: dense (384-dim) + sparse named vectors,
    plus payload indexes on `document_type` and `author` for fast filtering.

    Idempotent — safe to call on every startup.
    """
    settings = get_settings()
    client = get_qdrant_client()

    if client.collection_exists(settings.qdrant_collection):
        return

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={DENSE_VECTOR_NAME: VectorParams(size=DENSE_VECTOR_SIZE, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams()},
    )
    logger.info("Created Qdrant collection '%s'", settings.qdrant_collection)

    for field_name in FILTERABLE_PAYLOAD_FIELDS:
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name=field_name,
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info("Created payload index on '%s'", field_name)


# Backwards-compatible alias used by the ingestion pipeline (Step 2).
ensure_collection = setup_collection


def _chunk_to_point(chunk: KnowledgeChunk) -> PointStruct:
    if chunk.dense_embedding is None:
        raise ValueError(f"Chunk {chunk.chunk_id} has no dense_embedding; cannot upsert.")

    vector: dict[str, object] = {DENSE_VECTOR_NAME: chunk.dense_embedding}
    if chunk.sparse_embedding:
        vector[SPARSE_VECTOR_NAME] = SparseVector(
            indices=list(chunk.sparse_embedding.keys()),
            values=list(chunk.sparse_embedding.values()),
        )

    return PointStruct(
        id=str(chunk.chunk_id),
        vector=vector,
        payload={
            "parent_doc_id": str(chunk.parent_doc_id),
            "content": chunk.content,
            "document_id": str(chunk.metadata.document_id),
            "tenant_id": chunk.metadata.tenant_id,
            "source_uri": chunk.metadata.source_uri,
            "document_type": chunk.metadata.document_type.value,
            "author": chunk.metadata.author,
            "page_numbers": chunk.metadata.page_numbers,
        },
    )


def upsert_chunks_batch(chunks: list[KnowledgeChunk], batch_size: int = UPSERT_BATCH_SIZE) -> int:
    """Upsert embedded KnowledgeChunks into Qdrant in fixed-size batches.

    Returns the number of chunks successfully upserted. Raises on the first
    failed batch so the caller (a Celery task) can retry the whole document.
    """
    setup_collection()
    client = get_qdrant_client()
    settings = get_settings()

    upserted = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        points = [_chunk_to_point(c) for c in batch]
        client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)
        upserted += len(points)
        logger.info("Upserted Qdrant batch %d-%d (%d points)", start, start + len(points), len(points))

    return upserted


def _point_to_retrieved_chunk(point) -> RetrievedChunk:
    payload = point.payload or {}
    return RetrievedChunk(
        chunk_id=UUID(str(point.id)),
        parent_doc_id=UUID(payload["parent_doc_id"]),
        content=payload["content"],
        document_id=UUID(payload["document_id"]),
        tenant_id=payload["tenant_id"],
        source_uri=payload["source_uri"],
        document_type=DocumentType(payload["document_type"]),
        author=payload.get("author"),
        page_numbers=payload.get("page_numbers", []),
        score=point.score,
    )


def build_tenant_filter(tenant_id: str, document_type: str | None = None) -> Filter:
    """Mandatory authorization filter: every search is scoped to exactly one tenant.
    Never call search_similar without this (or an equivalent tenant-scoped filter).
    """
    must = [FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
    if document_type:
        must.append(FieldCondition(key="document_type", match=MatchValue(value=document_type)))
    return Filter(must=must)


def search_similar(
    query_vector: list[float], limit: int = 20, query_filter: Filter | None = None
) -> list[RetrievedChunk]:
    """Dense similarity search against the `dense` named vector.

    `query_filter` should always be built with `build_tenant_filter` (or include
    an equivalent tenant_id condition) — this is the authorization boundary
    enforced at the vector store, not just in application code.
    """
    settings = get_settings()
    client = get_qdrant_client()

    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        using=DENSE_VECTOR_NAME,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )
    return [_point_to_retrieved_chunk(point) for point in response.points]


def search_sparse(
    sparse_vector: dict[int, float], limit: int = 20, query_filter: Filter | None = None
) -> list[RetrievedChunk]:
    """Sparse-only similarity search against the `sparse` named vector.

    Added for Phase 6 evaluation (comparing dense vs. sparse vs. hybrid vs.
    hybrid+rerank) — the production retrieve() node in src/retrieval/graph.py
    currently only calls search_similar() (dense). Sparse vectors have been
    stored on every chunk since Step 2's ingestion but were never queried
    until now.
    """
    settings = get_settings()
    client = get_qdrant_client()

    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=SparseVector(indices=list(sparse_vector.keys()), values=list(sparse_vector.values())),
        using=SPARSE_VECTOR_NAME,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )
    return [_point_to_retrieved_chunk(point) for point in response.points]


def search_hybrid(
    dense_vector: list[float],
    sparse_vector: dict[int, float],
    limit: int = 20,
    prefetch_limit: int = 50,
    query_filter: Filter | None = None,
) -> list[RetrievedChunk]:
    """Hybrid search: dense + sparse candidates fused with Reciprocal Rank Fusion
    (Qdrant's native `query_points(..., query=FusionQuery(fusion=Fusion.RRF))`).

    Also new for Phase 6 evaluation — see search_sparse() docstring.
    """
    settings = get_settings()
    client = get_qdrant_client()

    response = client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(query=dense_vector, using=DENSE_VECTOR_NAME, limit=prefetch_limit, filter=query_filter),
            Prefetch(
                query=SparseVector(indices=list(sparse_vector.keys()), values=list(sparse_vector.values())),
                using=SPARSE_VECTOR_NAME,
                limit=prefetch_limit,
                filter=query_filter,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return [_point_to_retrieved_chunk(point) for point in response.points]


def delete_chunks_by_document(document_id: str) -> None:
    """Delete every chunk belonging to a document (used on document delete/reprocess)."""
    settings = get_settings()
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]),
    )
