import logging
import time
from collections.abc import AsyncGenerator

from src.api.dependencies import Principal
from src.api.schemas.chat import ChatRequest, ChatResponse, Citation
from src.core.cache import ChatResponseCache
from src.core.config import get_settings
from src.retrieval.graph import astream_rag_query, run_rag_query

logger = logging.getLogger(__name__)


def _cache() -> ChatResponseCache | None:
    settings = get_settings()
    return ChatResponseCache(default_ttl_seconds=settings.cache_ttl) if settings.cache_enabled else None


def _filters_dict(request: ChatRequest) -> dict:
    return {"document_type": request.filters.document_type} if request.filters else {}


async def get_chat_response(principal: Principal, request: ChatRequest) -> ChatResponse:
    """Non-streaming path: checks cache, else invokes the LangGraph workflow
    once and returns the full answer + citations. No retrieval/LLM logic
    lives here — it all stays in src/retrieval/graph.py.
    """
    filters = _filters_dict(request)
    cache = _cache()

    if cache is not None:
        cached = cache.get(
            tenant_id=principal.tenant_id, user_scope=principal.scopes, query=request.query, filters=filters
        )
        if cached is not None:
            logger.info("chat cache hit tenant=%s", principal.tenant_id)
            return ChatResponse(
                answer=cached["answer"],
                citations=[Citation(**c) for c in cached["citations"]],
                conversation_id=request.conversation_id,
                cached=True,
            )

    started = time.monotonic()
    result = await run_rag_query(
        request.query,
        principal.tenant_id,
        filters.get("document_type"),
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
    )
    logger.info(
        "chat_service: tenant=%s elapsed_s=%.2f is_relevant=%s iterations=%d",
        principal.tenant_id,
        time.monotonic() - started,
        result["is_relevant"],
        result["iteration_count"],
    )

    citations = [
        Citation(
            document_id=c.document_id,
            chunk_id=c.chunk_id,
            source_uri=c.source_uri,
            score=c.rerank_score if c.rerank_score is not None else c.score,
        )
        for c in result["reranked_docs"]
    ]

    if cache is not None:
        cache.set(
            tenant_id=principal.tenant_id,
            user_scope=principal.scopes,
            query=request.query,
            answer=result["final_answer"],
            citations=[c.model_dump(mode="json") for c in citations],
            filters=filters,
        )

    return ChatResponse(
        answer=result["final_answer"], citations=citations, conversation_id=request.conversation_id, cached=False
    )


async def stream_chat_response(principal: Principal, request: ChatRequest) -> AsyncGenerator[dict]:
    """Streaming path: yields SSE-ready event dicts {"event": ..., "data": {...}}.

    A cache hit is replayed through the SAME event protocol as a live
    generation (chunked into word-sized "tokens") so the client needs only
    one code path regardless of whether the answer was cached.
    """
    filters = _filters_dict(request)
    cache = _cache()

    if cache is not None:
        cached = cache.get(
            tenant_id=principal.tenant_id, user_scope=principal.scopes, query=request.query, filters=filters
        )
        if cached is not None:
            logger.info("chat cache hit (stream) tenant=%s", principal.tenant_id)
            for word in cached["answer"].split(" "):
                yield {"event": "token", "data": {"token": word + " "}}
            yield {"event": "citations", "data": {"sources": cached["citations"]}}
            yield {"event": "done", "data": {"status": "completed"}}
            return

    started = time.monotonic()
    tokens: list[str] = []
    citations_payload: list[dict] = []

    async for event in astream_rag_query(
        request.query,
        principal.tenant_id,
        filters.get("document_type"),
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
    ):
        if event["type"] == "token":
            tokens.append(event["token"])
            yield {"event": "token", "data": {"token": event["token"]}}
        elif event["type"] == "citations":
            citations_payload = event["sources"]
            yield {"event": "citations", "data": {"sources": event["sources"]}}
        elif event["type"] == "done":
            yield {"event": "done", "data": {"status": "completed"}}
        elif event["type"] == "error":
            yield {"event": "error", "data": {"code": event["code"], "message": event["message"]}}

    logger.info(
        "chat_service: tenant=%s elapsed_s=%.2f streamed_tokens=%d",
        principal.tenant_id,
        time.monotonic() - started,
        len(tokens),
    )

    full_answer = "".join(tokens)
    if cache is not None and full_answer:
        cache.set(
            tenant_id=principal.tenant_id,
            user_scope=principal.scopes,
            query=request.query,
            answer=full_answer,
            citations=citations_payload,
            filters=filters,
        )
