import asyncio
import logging
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import TypedDict

from groq import APITimeoutError as GroqTimeoutError
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from src.core.config import get_settings
from src.core.exceptions import AppError, LLMError, LLMTimeoutError, VectorStoreUnavailableError
from src.core.observability import configure_langsmith
from src.ingestion.embeddings import embed_query
from src.models.okf import RetrievedChunk
from src.observability.tracing import build_trace_config
from src.retrieval.qdrant_client import build_tenant_filter, search_similar
from src.retrieval.reranker import rerank_chunks

configure_langsmith()
logger = logging.getLogger(__name__)

MAX_ITERATIONS = 2
RETRIEVAL_TOP_K = 20
RERANK_TOP_K = 5


class RAGState(TypedDict):
    query: str
    original_query: str
    alternative_queries: list[str]
    tenant_id: str
    document_type_filter: str | None
    documents: list[RetrievedChunk]
    reranked_docs: list[RetrievedChunk]
    is_relevant: bool
    final_answer: str
    iteration_count: int


class QueryAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rewritten_query: str = Field(..., description="A clearer, self-contained rewrite of the user's query.")
    alternative_queries: list[str] = Field(
        ..., min_length=2, max_length=2, description="Exactly 2 alternative phrasings, different angles."
    )


class RelevanceGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_relevant: bool = Field(..., description="True only if the context is sufficient to answer the question.")
    reasoning: str = Field(..., description="One-sentence justification for the grade.")


@lru_cache
def get_llm() -> ChatGroq:
    """Cached ChatGroq client (llama-3.3-70b-versatile)."""
    settings = get_settings()
    return ChatGroq(api_key=settings.groq_api_key, model=settings.groq_model, temperature=0)


def with_backoff(runnable):
    """Wrap a full chain (prompt | llm, or prompt | structured_llm) with exponential
    backoff retry for transient rate-limit/network failures. Applied to the whole
    chain rather than the bare LLM, since RunnableRetry doesn't expose
    with_structured_output.
    """
    return runnable.with_retry(stop_after_attempt=3, wait_exponential_jitter=True)


def _format_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks))


def analyze_query(state: RAGState) -> dict:
    """Rewrite the query and generate 2 alternative phrasings for multi-query retrieval."""
    structured_llm = get_llm().with_structured_output(QueryAnalysis)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You rewrite questions for a document retrieval system. Rewrite the user's question to be "
                "clearer and self-contained, and generate exactly 2 alternative phrasings that approach the "
                "same question from different angles, for multi-query retrieval.",
            ),
            ("human", "{query}"),
        ]
    )
    try:
        analysis: QueryAnalysis = with_backoff(prompt | structured_llm).invoke({"query": state["query"]})
    except Exception:
        logger.error("analyze_query failed; retrieving with the original query only", exc_info=True)
        return {"original_query": state["query"], "alternative_queries": []}

    return {
        "original_query": state["query"],
        "query": analysis.rewritten_query,
        "alternative_queries": analysis.alternative_queries,
    }


def retrieve(state: RAGState) -> dict:
    """Dense similarity search in Qdrant for the rewritten query + alternatives, pooled to top 20.

    Every search is scoped to state["tenant_id"] via a mandatory Qdrant filter —
    this is the authorization boundary enforced at the vector store itself, not
    just in the API layer above it.
    """
    queries = [state["query"], *state.get("alternative_queries", [])]
    seen_ids: set[str] = set()
    pooled: list[RetrievedChunk] = []
    tenant_filter = build_tenant_filter(state["tenant_id"], document_type=state.get("document_type_filter"))

    failures = 0
    for q in queries:
        try:
            vector = embed_query(q)
            results = search_similar(vector, limit=RETRIEVAL_TOP_K, query_filter=tenant_filter)
        except Exception:
            failures += 1
            logger.error("retrieve: search failed for query '%s'", q, exc_info=True)
            continue

        for chunk in results:
            key = str(chunk.chunk_id)
            if key not in seen_ids:
                seen_ids.add(key)
                pooled.append(chunk)

    if failures == len(queries):
        # Every single search attempt failed — this is Qdrant being down, not
        # "no relevant chunks found". Surface it as a real failure (-> 503)
        # instead of silently falling through to the "not relevant" fallback.
        raise VectorStoreUnavailableError("The vector store is currently unavailable.")

    pooled.sort(key=lambda c: c.score, reverse=True)
    return {"documents": pooled[:RETRIEVAL_TOP_K]}


def rerank(state: RAGState) -> dict:
    """Cross-encoder rerank of the pooled candidates down to the top 5."""
    reranked = rerank_chunks(state["original_query"], state["documents"], top_k=RERANK_TOP_K)
    return {"reranked_docs": reranked}


def grade_context(state: RAGState) -> dict:
    """LLM grader: is the reranked context actually sufficient to answer the question?"""
    if not state["reranked_docs"]:
        return {"is_relevant": False}

    structured_llm = get_llm().with_structured_output(RelevanceGrade)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You grade whether retrieved context is sufficient to answer a user's question. Be strict: "
                "if the context is off-topic, too thin, or only tangentially related, grade it not relevant.",
            ),
            ("human", "Question: {query}\n\nContext:\n{context}"),
        ]
    )
    try:
        grade: RelevanceGrade = with_backoff(prompt | structured_llm).invoke(
            {"query": state["original_query"], "context": _format_context(state["reranked_docs"])}
        )
    except Exception:
        logger.error("grade_context failed; defaulting to not relevant", exc_info=True)
        return {"is_relevant": False}

    logger.info("grade_context: is_relevant=%s (%s)", grade.is_relevant, grade.reasoning)
    return {"is_relevant": grade.is_relevant}


MAX_STREAM_START_RETRIES = 3


async def _astream_with_retry(chain, inputs: dict) -> AsyncGenerator:
    """Stream a chain's output, retrying with exponential backoff only while
    trying to obtain the FIRST chunk. LangChain's with_retry() doesn't compose
    with streaming (it needs to buffer the whole call to know whether to
    retry), so once a chunk has actually been yielded — meaning it may already
    be on its way to an SSE client — we stop retrying and let errors propagate.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_STREAM_START_RETRIES):
        stream = chain.astream(inputs)
        try:
            first_chunk = await stream.__anext__()
        except StopAsyncIteration:
            return
        except Exception as exc:  # noqa: BLE001 - genuinely want to retry any transient failure here
            last_exc = exc
            logger.warning("LLM stream start failed (attempt %d/%d)", attempt + 1, MAX_STREAM_START_RETRIES)
            await asyncio.sleep(2**attempt)
            continue

        yield first_chunk
        async for chunk in stream:
            yield chunk
        return

    raise last_exc


async def generate(state: RAGState) -> dict:
    """Generate the final cited answer, streaming tokens via astream (so that when
    this node runs inside rag_graph.astream_events, each token is emitted as its
    own on_chat_model_stream event instead of appearing only once the full answer
    is ready). Falls back to a fixed message if nothing relevant was found.
    """
    if not state["is_relevant"]:
        logger.warning(
            "generate: no relevant context after %d iteration(s); returning fallback", state["iteration_count"]
        )
        return {
            "final_answer": (
                "I couldn't find reliable information in the knowledge base to answer this question "
                "confidently. Please rephrase your question or provide more context."
            )
        }

    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer the user's question using ONLY the numbered context below. Cite every claim with its "
                "source number using plain ASCII square brackets exactly like [1] or [2] (never full-width "
                "brackets, parentheses, or any other style). If the context only partially answers the "
                "question, say so explicitly rather than guessing.",
            ),
            ("human", "Question: {query}\n\nContext:\n{context}"),
        ]
    )
    chain = prompt | llm
    inputs = {"query": state["original_query"], "context": _format_context(state["reranked_docs"])}

    try:
        chunks = [chunk.content async for chunk in _astream_with_retry(chain, inputs)]
    except GroqTimeoutError as exc:
        logger.error("generate: LLM call timed out", exc_info=True)
        raise LLMTimeoutError("The language model timed out while generating a response.") from exc
    except Exception as exc:
        logger.error("generate failed", exc_info=True)
        raise LLMError("Unable to generate a response.") from exc

    normalized_answer = "".join(chunks).replace("【", "[").replace("】", "]")
    return {"final_answer": normalized_answer}


def rewrite_query(state: RAGState) -> dict:
    """Rewrite the query (broader terms / different phrasing) after a failed retrieval attempt."""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "The previous search query failed to retrieve relevant context for the user's question. "
                "Rewrite it to be broader, or use different terminology, so it is more likely to match "
                "relevant documents. Respond with ONLY the rewritten query, nothing else.",
            ),
            ("human", "Original question: {original_query}\nPrevious query: {query}"),
        ]
    )
    try:
        response = with_backoff(prompt | llm).invoke(
            {"original_query": state["original_query"], "query": state["query"]}
        )
        new_query = response.content.strip()
    except Exception:
        logger.error("rewrite_query failed; reusing the previous query", exc_info=True)
        new_query = state["query"]

    return {"query": new_query, "iteration_count": state["iteration_count"] + 1}


def route_after_grading(state: RAGState) -> str:
    """Conditional edge out of grade_context."""
    if state["is_relevant"]:
        return "generate"
    if state["iteration_count"] < MAX_ITERATIONS:
        return "rewrite_query"
    return "generate"  # exhausted retries -> generate() emits the fallback message


def build_rag_graph():
    graph = StateGraph(RAGState)

    graph.add_node("analyze_query", analyze_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("rerank", rerank)
    graph.add_node("grade_context", grade_context)
    graph.add_node("generate", generate)
    graph.add_node("rewrite_query", rewrite_query)

    graph.add_edge(START, "analyze_query")
    graph.add_edge("analyze_query", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "grade_context")
    graph.add_conditional_edges(
        "grade_context",
        route_after_grading,
        {"generate": "generate", "rewrite_query": "rewrite_query"},
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate", END)

    return graph.compile()


rag_graph = build_rag_graph()


def _initial_state(query: str, tenant_id: str, document_type_filter: str | None = None) -> RAGState:
    return {
        "query": query,
        "original_query": query,
        "alternative_queries": [],
        "tenant_id": tenant_id,
        "document_type_filter": document_type_filter,
        "documents": [],
        "reranked_docs": [],
        "is_relevant": False,
        "final_answer": "",
        "iteration_count": 0,
    }


async def run_rag_query(
    query: str,
    tenant_id: str,
    document_type_filter: str | None = None,
    *,
    conversation_id: str | None = None,
    request_id: str | None = None,
) -> RAGState:
    """Entry point: run a single question through the full RAG graph (non-streaming).

    conversation_id/request_id are purely for LangSmith trace metadata (see
    observability/tracing.py) — metadata attached at this top-level call is
    inherited by every nested node and LLM run in the trace.
    """
    trace_config = build_trace_config(
        request_id=request_id, conversation_id=conversation_id, tenant_id=tenant_id, retrieval_strategy="dense"
    )
    return await rag_graph.ainvoke(_initial_state(query, tenant_id, document_type_filter), config=trace_config)


def _citation_payload(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "document_id": str(c.document_id),
            "chunk_id": str(c.chunk_id),
            "source_uri": c.source_uri,
            "score": c.rerank_score if c.rerank_score is not None else c.score,
        }
        for c in chunks
    ]


async def astream_rag_query(
    query: str,
    tenant_id: str,
    document_type_filter: str | None = None,
    *,
    conversation_id: str | None = None,
    request_id: str | None = None,
) -> AsyncGenerator[dict]:
    """Streaming entry point: runs the same compiled graph via astream_events and
    yields plain event dicts the API layer turns into SSE events:
      {"type": "token", "token": "..."}
      {"type": "citations", "sources": [...]}
      {"type": "done"}
      {"type": "error", "code": "...", "message": "..."}

    Token events come from the `generate` node's own astream() call (see
    generate() above) surfacing as on_chat_model_stream events — no separate
    retrieval or LLM logic is implemented here, this just listens to the graph.
    """
    initial_state = _initial_state(query, tenant_id, document_type_filter)
    last_reranked: list[RetrievedChunk] = []
    any_token_yielded = False
    # generate() skips the LLM entirely for the "no relevant context" fallback
    # (see generate() above) — no on_chat_model_stream events fire for it, so
    # without this, the fallback message would silently never reach an SSE
    # client. Captured from the node's own on_chain_end so it's available to
    # emit as a single token after the loop if nothing else streamed.
    fallback_answer: str | None = None
    trace_config = build_trace_config(
        request_id=request_id, conversation_id=conversation_id, tenant_id=tenant_id, retrieval_strategy="dense"
    )

    try:
        async for event in rag_graph.astream_events(initial_state, version="v2", config=trace_config):
            kind = event["event"]

            if kind == "on_chain_end" and event.get("name") == "rerank":
                output = event["data"].get("output") or {}
                reranked = output.get("reranked_docs")
                if reranked:
                    last_reranked = reranked

            elif kind == "on_chain_end" and event.get("name") == "generate":
                output = event["data"].get("output") or {}
                fallback_answer = output.get("final_answer")

            elif kind == "on_chat_model_stream" and event.get("metadata", {}).get("langgraph_node") == "generate":
                chunk = event["data"]["chunk"]
                token = (chunk.content or "").replace("【", "[").replace("】", "]")
                if token:
                    any_token_yielded = True
                    yield {"type": "token", "token": token}

        if not any_token_yielded and fallback_answer:
            yield {"type": "token", "token": fallback_answer}

        if last_reranked:
            yield {"type": "citations", "sources": _citation_payload(last_reranked)}

        yield {"type": "done"}

    except AppError as exc:
        logger.error("astream_rag_query failed for query=%r: %s", query, exc.error_code, exc_info=True)
        yield {"type": "error", "code": exc.error_code, "message": exc.message}
    except Exception:
        logger.error("astream_rag_query failed for query=%r", query, exc_info=True)
        yield {"type": "error", "code": "LLM_ERROR", "message": "Unable to generate response"}
