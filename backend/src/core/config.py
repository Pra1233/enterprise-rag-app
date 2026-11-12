from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized, typed application configuration loaded from environment/.env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Enterprise RAG API"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"

    # --- Auth (JWT) ---
    # Dev-only shared secret for HS256. Replace with an asymmetric key + real IdP
    # (Auth0/Cognito/etc.) before production; the dependency interface in
    # src/api/dependencies.py is written to make that swap a one-function change.
    jwt_secret_key: str = Field(..., description="HS256 signing secret for access tokens.")
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # --- Groq LLM (free tier) ---
    groq_api_key: str = Field(..., description="API key for Groq (free tier, no credit card).")
    # llama-3.3-70b-versatile was retired from Groq's free-tier catalog; openai/gpt-oss-120b
    # is the current largest free model there. Override via GROQ_MODEL if Groq's lineup changes again.
    groq_model: str = "openai/gpt-oss-120b"
    groq_timeout_seconds: float = 30.0

    # --- Local embeddings / reranker (free, no API key) ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    embedding_device: str = "cpu"

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "enterprise_rag_chunks"
    qdrant_timeout_seconds: float = 10.0

    # --- PostgreSQL ---
    postgres_url: str = "postgresql+psycopg2://rag_user:rag_password@localhost:5432/rag_db"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"

    # --- MinIO (S3-compatible object storage for original documents) ---
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "rag-documents"
    minio_secure: bool = False

    # --- Response cache ---
    cache_enabled: bool = True
    cache_ttl: int = 86400

    # --- Upload limits ---
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    allowed_upload_extensions: tuple[str, ...] = (".pdf",)

    # --- LangSmith tracing ---
    # LANGSMITH_* is the current LangSmith SDK convention (supersedes the older
    # LANGCHAIN_TRACING_V2/LANGCHAIN_API_KEY/LANGCHAIN_PROJECT names used in
    # earlier phases); configure_langsmith() in core/observability.py sets both
    # so tracing works regardless of which the installed SDK version prefers.
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "rag-production"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # --- Evaluation (Phase 6) ---
    evaluation_enabled: bool = True
    evaluation_dataset_path: str = "src/evaluation/datasets/sample_dataset.json"
    evaluation_top_k: int = 5
    evaluation_max_concurrency: int = 2

    # --- Metrics ---
    metrics_enabled: bool = True

    @property
    def celery_broker_url(self) -> str:
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        return self.redis_url


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-parsing env on every import."""
    return Settings()
