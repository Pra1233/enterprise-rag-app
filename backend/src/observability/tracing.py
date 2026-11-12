"""Helpers for attaching LangSmith trace metadata to LangGraph runs.

LangChain/LangGraph accept an optional `config={"metadata": ..., "tags": ...}`
on invoke/ainvoke/astream_events calls. Metadata set at the top-level graph
call is inherited by every nested node and LLM run it contains — this is how
query analysis, retrieval, reranking, grading and generation all end up
carrying this metadata in LangSmith without instrumenting each node by hand.
"""

import uuid
from typing import Any


def build_trace_config(
    *,
    request_id: str | None = None,
    conversation_id: str | None = None,
    tenant_id: str | None = None,
    document_ids: list[str] | None = None,
    retrieval_strategy: str = "dense",
) -> dict[str, Any]:
    """Build a LangChain `config` dict carrying safe, non-sensitive trace metadata.

    Deliberately excludes API keys, raw document/chunk content, and anything
    that could be PII — only identifiers and a strategy label are attached.
    Model name, execution duration and (when the provider reports it) token
    usage are captured separately by LangChain's own callback system and by
    observability/metrics.py — they are not duplicated here.
    """
    metadata: dict[str, Any] = {
        "request_id": request_id or str(uuid.uuid4()),
        "retrieval_strategy": retrieval_strategy,
    }
    if conversation_id:
        metadata["conversation_id"] = conversation_id
    if tenant_id:
        metadata["tenant_id"] = tenant_id
    if document_ids:
        metadata["document_ids"] = document_ids

    return {
        "metadata": metadata,
        "tags": ["rag-pipeline", retrieval_strategy],
        "run_name": "rag_query",
    }
