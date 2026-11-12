"""Re-exports the shared domain exceptions for API route/service code.

The classes themselves live in src/core/exceptions.py since graph.py and the
ingestion pipeline (outside the api/ package) need to raise them too; this
module exists so existing `from src.api.exceptions import X` call sites keep
working unchanged.
"""

from src.core.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    DuplicateDocumentError,
    ForbiddenError,
    LLMError,
    LLMTimeoutError,
    NotFoundError,
    QuotaExceededError,
    UnauthorizedError,
    ValidationFailedError,
    VectorStoreUnavailableError,
)

__all__ = [
    "AppError",
    "BadRequestError",
    "ConflictError",
    "DuplicateDocumentError",
    "ForbiddenError",
    "LLMError",
    "LLMTimeoutError",
    "NotFoundError",
    "QuotaExceededError",
    "UnauthorizedError",
    "ValidationFailedError",
    "VectorStoreUnavailableError",
]
