from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    original_filename: str
    document_type: str
    author: str | None
    status: str
    error_message: str | None
    file_size_bytes: int
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class ReprocessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    task_id: str
    status: str
    message: str


class DeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    status: str
    message: str
