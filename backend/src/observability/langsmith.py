"""LangSmith tracing configuration for the RAG pipeline.

Reuses src.core.observability.configure_langsmith() (the single place env
vars are set — see that module for why both LANGSMITH_* and the older
LANGCHAIN_* names are set) rather than re-implementing it here, per the
instruction not to create a second implementation of existing functionality.
"""

from src.core.observability import configure_langsmith
from src.observability.tracing import build_trace_config

__all__ = ["configure_langsmith", "build_trace_config"]
