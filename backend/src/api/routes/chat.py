import asyncio
import json
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from src.api.dependencies import CurrentPrincipal, Principal
from src.api.quota import EnforceLlmQuota
from src.api.schemas.chat import ChatRequest, ChatResponse
from src.services.chat_service import get_chat_response, stream_chat_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

HEARTBEAT_INTERVAL_SECONDS = 15


def _format_sse(event: str, data: dict) -> str:
    # SSE requires UTF-8 text frames; ensure_ascii=False keeps citations/answers
    # with non-ASCII characters intact instead of \uXXXX-escaping them.
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _sse_event_generator(request: Request, principal: Principal, chat_request: ChatRequest):
    """Drives stream_chat_response() -> SSE frames.

    Checks for client disconnects every iteration (never accumulates the full
    answer first), and emits a `: heartbeat` comment frame if no real event
    arrives within HEARTBEAT_INTERVAL_SECONDS, so intermediate proxies don't
    time out an idle-looking connection while the LLM is still "thinking".
    """
    agen = stream_chat_response(principal, chat_request).__aiter__()
    try:
        while True:
            if await request.is_disconnected():
                logger.info("Client disconnected mid-stream for tenant=%s; stopping generation", principal.tenant_id)
                return

            try:
                item = await asyncio.wait_for(agen.__anext__(), timeout=HEARTBEAT_INTERVAL_SECONDS)
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            except StopAsyncIteration:
                return

            yield _format_sse(item["event"], item["data"])
    except Exception:
        # Stream has already started (headers sent) — an HTTP error response is
        # no longer possible, so the only way to signal failure is an SSE event.
        # Never include the exception's own message: it may carry internals.
        logger.error("Unhandled error during SSE stream for tenant=%s", principal.tenant_id, exc_info=True)
        yield _format_sse("error", {"code": "LLM_ERROR", "message": "Unable to generate response"})


@router.post("", response_model=None)
async def chat(
    chat_request: ChatRequest,
    request: Request,
    response: Response,
    principal: Principal = CurrentPrincipal,
    _quota: None = EnforceLlmQuota,
) -> ChatResponse | StreamingResponse:
    """RAG chat endpoint. Non-streaming by default is a plain ChatResponse;
    `stream: true` returns a text/event-stream of token/citations/done events.

    One quota unit is consumed per call regardless of streaming mode or cache
    hits — the quota is on "chat messages" as a user-facing concept, not on
    literal LLM API calls, which also prevents gaming the limit via repeated
    cached queries.

    All retrieval + LLM orchestration lives in src/retrieval/graph.py via
    chat_service.py — this route only handles the HTTP/SSE transport.
    """
    if not chat_request.stream:
        return await get_chat_response(principal, chat_request)

    return StreamingResponse(
        _sse_event_generator(request, principal, chat_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            **response.headers,
        },
    )
