import uuid

from sqlalchemy.orm import Session

from src.api.exceptions import ConflictError, NotFoundError
from src.api.schemas.admin import (
    AdminAuditLogEntry,
    AdminAuditLogResponse,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
)
from src.core.db import LoginAuditLog, User
from src.core.security import hash_password


def list_users(db: Session) -> list[AdminUserOut]:
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [AdminUserOut.model_validate(u) for u in users]


def create_user(db: Session, payload: AdminUserCreate) -> AdminUserOut:
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise ConflictError(f"Username '{payload.username}' is already taken.")

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        llm_request_limit=payload.llm_request_limit,
        upload_limit=payload.upload_limit,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AdminUserOut.model_validate(user)


def update_user(db: Session, user_id: uuid.UUID, payload: AdminUserUpdate) -> AdminUserOut:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"No user found with id={user_id}.")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return AdminUserOut.model_validate(user)


def list_audit_log(db: Session, page: int, page_size: int) -> AdminAuditLogResponse:
    query = db.query(LoginAuditLog, User).join(User, LoginAuditLog.user_id == User.id)
    total = query.count()
    rows = query.order_by(LoginAuditLog.logged_in_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        AdminAuditLogEntry(
            id=log.id,
            username=log.username,
            logged_in_at=log.logged_in_at,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            llm_requests_used=user.llm_requests_used,
            llm_request_limit=user.llm_request_limit,
            uploads_used=user.uploads_used,
            upload_limit=user.upload_limit,
        )
        for log, user in rows
    ]
    return AdminAuditLogResponse(items=items, total=total, page=page, page_size=page_size)
