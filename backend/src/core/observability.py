import os

from src.core.config import get_settings


def configure_langsmith() -> None:
    """Wire up LangSmith tracing from settings. Every ChatGroq/LCEL call made
    after this runs is automatically traced — no per-call instrumentation needed.

    Sets both the current LANGSMITH_* env vars and the older LANGCHAIN_* names,
    since different langchain-core/langsmith SDK versions have checked one or
    the other as primary; setting both is the compatible-either-way choice.
    """
    settings = get_settings()

    if not settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
