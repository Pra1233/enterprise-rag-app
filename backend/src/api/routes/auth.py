import logging

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from src.api.dependencies import CurrentPrincipal, DbSession, Principal
from src.api.schemas.auth import LoginRequest, LoginResponse, UserOut
from src.services.auth_service import login as login_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, db: Session = DbSession) -> LoginResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return login_service(db, payload, ip_address, user_agent)


@router.get("/me", response_model=UserOut)
async def me(principal: Principal = CurrentPrincipal) -> UserOut:
    return UserOut(
        id=principal.user_id,
        username=principal.username,
        role=principal.role,
        llm_request_limit=principal.llm_request_limit,
        llm_requests_used=principal.llm_requests_used,
        upload_limit=principal.upload_limit,
        uploads_used=principal.uploads_used,
        is_active=True,
    )
