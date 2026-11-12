import logging
import uuid

from fastapi import Depends, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from src.api.dependencies import CurrentPrincipal, DbSession, Principal
from src.api.exceptions import QuotaExceededError
from src.core.db import User

logger = logging.getLogger(__name__)


def _enforce(
    db: Session,
    response: Response,
    principal: Principal,
    *,
    used_column,
    limit_column,
    resource: str,
    noun: str,
    unit: str,
) -> None:
    # Admins manage the system and aren't throttled by a quota they themselves control.
    if principal.role == "admin":
        return

    user_id = uuid.UUID(principal.user_id)
    stmt = (
        update(User)
        .where(User.id == user_id, used_column < limit_column)
        .values(**{used_column.key: used_column + 1})
        .returning(used_column, limit_column)
    )
    result = db.execute(stmt).first()
    db.commit()

    if result is None:
        current = db.get(User, user_id)
        used = getattr(current, used_column.key) if current else 0
        limit = getattr(current, limit_column.key) if current else 0
        raise QuotaExceededError(
            f"{noun} limit reached ({used}/{limit} {unit}). Contact your administrator to request a higher limit."
        )

    used, limit = result
    response.headers["X-Quota-Used"] = str(used)
    response.headers["X-Quota-Limit"] = str(limit)
    response.headers["X-Quota-Resource"] = resource


def enforce_upload_quota(response: Response, db: Session = DbSession, principal: Principal = CurrentPrincipal) -> None:
    _enforce(
        db,
        response,
        principal,
        used_column=User.uploads_used,
        limit_column=User.upload_limit,
        resource="uploads",
        noun="Upload",
        unit="documents",
    )


def enforce_llm_quota(response: Response, db: Session = DbSession, principal: Principal = CurrentPrincipal) -> None:
    _enforce(
        db,
        response,
        principal,
        used_column=User.llm_requests_used,
        limit_column=User.llm_request_limit,
        resource="llm_requests",
        noun="Chat message",
        unit="messages",
    )


EnforceUploadQuota = Depends(enforce_upload_quota)
EnforceLlmQuota = Depends(enforce_llm_quota)
