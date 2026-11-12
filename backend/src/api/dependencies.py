import logging
import uuid
from collections.abc import Generator

import jwt
from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.api.exceptions import ForbiddenError, UnauthorizedError
from src.core.config import get_settings
from src.core.db import SessionLocal, User

logger = logging.getLogger(__name__)


class Principal(BaseModel):
    """The authenticated caller, resolved server-side from a live User row.

    Never construct this from client-supplied headers/body fields directly —
    every field here is read from the database, keyed only by the
    signature-verified token's `sub` claim. A token's other claims (role,
    tenant_id, ...) are decoded but intentionally ignored for anything
    security-relevant, since they could go stale if an admin changes a
    user's role/limits/active-status after the token was issued.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    tenant_id: str
    username: str
    role: str
    scopes: list[str] = []
    llm_request_limit: int = 0
    llm_requests_used: int = 0
    upload_limit: int = 0
    uploads_used: int = 0


def get_db() -> Generator[Session]:
    """FastAPI dependency yielding a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_principal(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Principal:
    """Resolve and verify the caller's identity from a Bearer JWT, then load
    their live User row — the token's signature only proves the server
    minted it; the row is the source of truth for role/limits/active status.

    This is the one place token verification happens — swapping HS256/shared-secret
    for RS256 + a real IdP's JWKS later only touches this function, not any route
    or service that depends on Principal.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1].strip()
    settings = get_settings()

    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token.") from exc

    sub = claims.get("sub")
    if not sub:
        raise UnauthorizedError("Token is missing required claim (sub).")

    try:
        user_id = uuid.UUID(str(sub))
    except ValueError as exc:
        raise UnauthorizedError("Invalid token subject.") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired session.")

    return Principal(
        user_id=str(user.id),
        tenant_id=str(user.id),
        username=user.username,
        role=user.role,
        scopes=[user.role],
        llm_request_limit=user.llm_request_limit,
        llm_requests_used=user.llm_requests_used,
        upload_limit=user.upload_limit,
        uploads_used=user.uploads_used,
    )


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.role != "admin":
        raise ForbiddenError("Admin privileges required.")
    return principal


CurrentPrincipal = Depends(get_current_principal)
RequireAdmin = Depends(require_admin)
DbSession = Depends(get_db)
