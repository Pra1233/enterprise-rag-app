import logging

from fastapi import APIRouter
from sqlalchemy import text

from src.core.config import get_settings
from src.core.db import engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe: process is up. Does not check dependencies."""
    settings = get_settings()
    return {"status": "ok", "environment": settings.app_env}


@router.get("/health/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe: can the API actually serve requests right now."""
    checks = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        logger.warning("Readiness check: Postgres unavailable", exc_info=True)
        checks["postgres"] = "unavailable"
    return checks
