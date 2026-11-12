import logging

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy.orm import Session

from src.api.dependencies import CurrentPrincipal, DbSession, Principal
from src.api.quota import EnforceUploadQuota
from src.api.schemas.ingestion import IngestionMetadataIn, IngestionStatusResponse, UploadResponse
from src.services.ingestion_service import get_ingestion_status, upload_and_queue_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    author: str | None = Form(default=None),
    collection: str | None = Form(default=None),
    db: Session = DbSession,
    principal: Principal = CurrentPrincipal,
    _quota: None = EnforceUploadQuota,
) -> UploadResponse:
    """Validates and stores the file, enqueues ingestion, and returns immediately.
    Parsing/chunking/embedding all happen in the Celery worker, never here.
    """
    content = await file.read()
    metadata = IngestionMetadataIn(author=author, collection=collection)
    return upload_and_queue_document(db, principal, file.filename or "upload.pdf", content, metadata)


@router.get("/status/{task_id}", response_model=IngestionStatusResponse)
async def ingestion_status(
    task_id: str, db: Session = DbSession, principal: Principal = CurrentPrincipal
) -> IngestionStatusResponse:
    return get_ingestion_status(db, principal, task_id)
