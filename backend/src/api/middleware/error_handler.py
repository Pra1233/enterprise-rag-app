import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.exceptions import AppError

logger = logging.getLogger(__name__)


def _error_body(request: Request, code: str, message: str) -> dict:
    request_id = getattr(request.state, "request_id", None) or "unknown"
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def register_exception_handlers(app: FastAPI) -> None:
    """Centralized exception -> HTTP response mapping.

    Every handler here returns a plain, client-safe message — stack traces,
    internal paths, and exception args from third-party clients (Qdrant,
    Groq, boto/minio) are logged (with the request_id for correlation) but
    never serialized into the response body.
    """

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error(
                "request_id=%s app_error=%s message=%s",
                getattr(request.state, "request_id", "unknown"),
                exc.error_code,
                exc.message,
                exc_info=True,
            )
        else:
            logger.warning(
                "request_id=%s app_error=%s message=%s",
                getattr(request.state, "request_id", "unknown"),
                exc.error_code,
                exc.message,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, exc.error_code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(request, "VALIDATION_ERROR", "Request validation failed."),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, "HTTP_ERROR", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error("request_id=%s unhandled_exception=%s", request_id, type(exc).__name__, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(request, "INTERNAL_ERROR", "An unexpected error occurred."),
        )


async def request_id_middleware(request: Request, call_next):
    """Attach a request_id to every request for log correlation, and echo it
    back as a response header so clients can report it when filing issues.
    """
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response
