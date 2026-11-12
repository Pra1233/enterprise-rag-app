import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import DbSession, require_admin
from src.api.schemas.admin import (
    AdminAuditLogResponse,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
)
from src.services import admin_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(db: Session = DbSession) -> list[AdminUserOut]:
    return admin_service.list_users(db)


@router.post("/users", response_model=AdminUserOut, status_code=201)
async def create_user(payload: AdminUserCreate, db: Session = DbSession) -> AdminUserOut:
    return admin_service.create_user(db, payload)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(user_id: uuid.UUID, payload: AdminUserUpdate, db: Session = DbSession) -> AdminUserOut:
    return admin_service.update_user(db, user_id, payload)


@router.get("/audit-log", response_model=AdminAuditLogResponse)
async def audit_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = DbSession,
) -> AdminAuditLogResponse:
    return admin_service.list_audit_log(db, page, page_size)
