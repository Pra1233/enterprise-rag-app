"""Domain-level exceptions, shared by the retrieval/ingestion pipeline and the
API layer. src/api/middleware/error_handler.py maps these to HTTP status
codes; src/api/exceptions.py re-exports them for route/service code.
"""


class AppError(Exception):
    """Base class for all application errors the error handler understands."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationFailedError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class BadRequestError(AppError):
    status_code = 400
    error_code = "BAD_REQUEST"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class DuplicateDocumentError(AppError):
    status_code = 409
    error_code = "DUPLICATE_DOCUMENT"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"


class QuotaExceededError(AppError):
    status_code = 429
    error_code = "QUOTA_EXCEEDED"


class VectorStoreUnavailableError(AppError):
    status_code = 503
    error_code = "VECTOR_STORE_UNAVAILABLE"


class LLMTimeoutError(AppError):
    status_code = 504
    error_code = "LLM_TIMEOUT"


class LLMError(AppError):
    status_code = 502
    error_code = "LLM_ERROR"
