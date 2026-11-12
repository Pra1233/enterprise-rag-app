import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.error_handler import register_exception_handlers, request_id_middleware
from src.api.routes import admin, auth, chat, documents, health, ingestion
from src.core.config import get_settings
from src.core.observability import configure_langsmith

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s starting up in '%s' mode", settings.app_name, settings.app_env)
    configure_langsmith()

    # Best-effort warm-up: make sure the Qdrant collection exists before the
    # first request needs it. Never fail startup over this — Qdrant may still
    # be coming up in docker-compose, and individual requests will surface a
    # clear 503 (VectorStoreUnavailableError) if it's genuinely down.
    try:
        from src.retrieval.qdrant_client import setup_collection

        setup_collection()
    except Exception:
        logger.warning("Qdrant collection setup failed at startup; will retry lazily per-request", exc_info=True)

    yield

    logger.info("%s shutting down", settings.app_name)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_id_middleware)
register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(ingestion.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
