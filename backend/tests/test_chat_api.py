import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

from src.api.dependencies import Principal
from src.api.routes.chat import _sse_event_generator
from src.api.schemas.chat import ChatRequest
from src.core.cache import ChatResponseCache
from src.core.exceptions import LLMTimeoutError, VectorStoreUnavailableError
from src.models.okf import DocumentType, RetrievedChunk
from tests.conftest import _resolve_identity


def _fake_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        parent_doc_id=uuid.uuid4(),
        content="Project Aurora is led by Dr. Vasquez.",
        document_id=uuid.uuid4(),
        tenant_id="tenant-1",
        source_uri="tenant-1/doc.pdf",
        document_type=DocumentType.PDF,
        author=None,
        page_numbers=[0],
        score=0.9,
        rerank_score=0.95,
    )


def test_successful_non_streaming_chat(client, auth_headers, monkeypatch):
    """7. Successful non-streaming chat."""
    chunk = _fake_chunk()
    fake_state = {
        "final_answer": "Project Aurora is led by Dr. Vasquez [1].",
        "reranked_docs": [chunk],
        "is_relevant": True,
        "iteration_count": 0,
    }
    monkeypatch.setattr("src.services.chat_service.run_rag_query", AsyncMock(return_value=fake_state))

    response = client.post(
        "/api/v1/chat", json={"query": "Who leads Project Aurora?", "stream": False}, headers=auth_headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "Dr. Vasquez" in body["answer"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["chunk_id"] == str(chunk.chunk_id)
    assert body["cached"] is False


async def _fake_astream(*args, **kwargs):
    yield {"type": "token", "token": "RAG"}
    yield {"type": "token", "token": " works."}
    yield {"type": "citations", "sources": [{"document_id": "d1", "chunk_id": "c1", "source_uri": "u", "score": 0.9}]}
    yield {"type": "done"}


def test_successful_sse_streaming(client, auth_headers, monkeypatch):
    """8. Successful SSE streaming."""
    monkeypatch.setattr("src.services.chat_service.astream_rag_query", _fake_astream)

    response = client.post("/api/v1/chat", json={"query": "What is RAG?", "stream": True}, headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"

    body = response.text
    assert "event: token" in body
    assert '"token": "RAG"' in body
    assert "event: citations" in body
    assert "event: done" in body


def test_cached_response_retrieval(client, auth_headers, monkeypatch):
    """9. Cached response retrieval — a cache hit skips the LangGraph call entirely."""
    cache = ChatResponseCache(default_ttl_seconds=86400)
    cache.set(
        # auth_headers' principal.tenant_id is always its own (real) user id
        # now, not the literal string "tenant-1" — see conftest._IDENTITY_IDS.
        tenant_id=str(_resolve_identity("tenant-1")),
        # auth_headers' principal.scopes is now [user.role] ("user"), not the
        # empty list the old trust-the-token-claims model defaulted to.
        user_scope=["user"],
        query="What is RAG?",
        answer="RAG stands for Retrieval-Augmented Generation.",
        citations=[],
        filters={},
    )

    mock_run = AsyncMock()
    monkeypatch.setattr("src.services.chat_service.run_rag_query", mock_run)

    response = client.post("/api/v1/chat", json={"query": "What is RAG?", "stream": False}, headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cached"] is True
    assert "Retrieval-Augmented" in body["answer"]
    mock_run.assert_not_called()


def test_qdrant_unavailable_returns_503(client, auth_headers, monkeypatch):
    """11. Qdrant unavailable -> 503."""

    async def _raise(*a, **k):
        raise VectorStoreUnavailableError("down")

    monkeypatch.setattr("src.services.chat_service.run_rag_query", _raise)

    response = client.post("/api/v1/chat", json={"query": "test", "stream": False}, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "VECTOR_STORE_UNAVAILABLE"


def test_llm_timeout_returns_504(client, auth_headers, monkeypatch):
    """12. LLM timeout -> 504."""

    async def _raise(*a, **k):
        raise LLMTimeoutError("timed out")

    monkeypatch.setattr("src.services.chat_service.run_rag_query", _raise)

    response = client.post("/api/v1/chat", json={"query": "test", "stream": False}, headers=auth_headers)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "LLM_TIMEOUT"


def test_client_disconnection_stops_stream(monkeypatch):
    """13. Client disconnection during streaming: the generator must stop
    immediately and never pull an item from the underlying event source —
    i.e. we do not keep generating tokens nobody will receive.
    """
    consumed = []

    async def _fake_stream(*a, **k):
        consumed.append(True)
        yield {"event": "token", "data": {"token": "should not be read"}}

    monkeypatch.setattr("src.api.routes.chat.stream_chat_response", _fake_stream)

    fake_request = MagicMock()
    fake_request.is_disconnected = AsyncMock(return_value=True)

    principal = Principal(user_id="user-1", tenant_id="tenant-1", username="user-1", role="user")
    chat_request = ChatRequest(query="test", stream=True)

    async def run():
        return [frame async for frame in _sse_event_generator(fake_request, principal, chat_request)]

    events = asyncio.run(run())

    assert events == []
    assert consumed == []
