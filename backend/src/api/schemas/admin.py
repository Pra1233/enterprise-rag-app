from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas.auth import UserOut


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=256)
    role: Literal["admin", "user"] = "user"
    llm_request_limit: int = Field(default=200, ge=0)
    upload_limit: int = Field(default=20, ge=0)


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["admin", "user"] | None = None
    llm_request_limit: int | None = Field(default=None, ge=0)
    upload_limit: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class AdminUserOut(UserOut):
    created_at: datetime


class AdminAuditLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    username: str
    logged_in_at: datetime
    ip_address: str | None
    user_agent: str | None
    llm_requests_used: int
    llm_request_limit: int
    uploads_used: int
    upload_limit: int


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AdminAuditLogEntry]
    total: int
    page: int
    page_size: int
