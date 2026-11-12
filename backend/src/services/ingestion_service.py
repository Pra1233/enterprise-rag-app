import hashlib
import logging
import uuid

from sqlalchemy.orm import Session

from src.api.dependencies import Principal
from src.api.exceptions import BadRequestError, DuplicateDocumentError, NotFoundError
from src.api.schemas.ingestion import IngestionMetadataIn, IngestionStatusResponse, UploadResponse
from src.core.config import get_settings
from src.core.db import DocumentRecord
from src.core.storage import ensure_bucket, upload_document
from src.ingestion.tasks import ingest_document_task
from src.ingestion.worker import celery_app
from src.models.okf import DocumentType

logger = logging.getLogger(__name__)

# Stages reported back to the client, in pipeline order.
_KNOWN_STAGES = ("queued", "parsing", "chunking", "embedding", "indexed", "failed")


def _validate_upload(filename: str, size_bytes: int) -> None:
    settings = get_settings()
    if size_bytes > settings.max_upload_size_bytes:
        raise BadRequestError(f"File too large ({size_bytes} bytes); max is {settings.max_upload_size_bytes} bytes.")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_upload_extensions:
        raise BadRequestError(f"Unsupported file type '{ext}'. Allowed: {settings.allowed_upload_extensions}.")


def upload_and_queue_document(
    db: Session,
    principal: Principal,
    filename: str,
    content: bytes,
    metadata: IngestionMetadataIn,
) -> UploadResponse:
    """Validate, hash, store in MinIO, create the DB record, and enqueue ingestion.

    Deliberately does NOT parse the document or generate embeddings here —
    that happens entirely in the Celery worker (ingest_document_task), so the
    HTTP request returns as soon as the file is durably stored and queued.
    """
    _validate_upload(filename, len(content))
    content_hash = hashlib.sha256(content).hexdigest()

    existing = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.tenant_id == principal.tenant_id, DocumentRecord.content_hash == content_hash)
        .first()
    )
    if existing is not None:
        raise DuplicateDocumentError(
            f"An identical document already exists (document_id={existing.id}, status={existing.status})."
        )

    document_id = uuid.uuid4()
    object_key = f"{principal.tenant_id}/{document_id}/{filename}"

    ensure_bucket()
    upload_document(object_key, content, content_type="application/pdf")

    db_record = DocumentRecord(
        id=document_id,
        tenant_id=principal.tenant_id,
        owner_id=principal.user_id,
        source_uri=object_key,
        document_type=DocumentType.PDF.value,
        author=metadata.author,
        original_filename=filename,
        file_size_bytes=len(content),
        content_hash=content_hash,
        storage_path=object_key,
        status="queued",
    )
    db.add(db_record)
    db.commit()

    async_result = ingest_document_task.delay(str(document_id))
    db_record.celery_task_id = async_result.id
    db.commit()

    return UploadResponse(
        document_id=document_id, task_id=async_result.id, status="queued", message="Document ingestion started"
    )


def get_ingestion_status(db: Session, principal: Principal, task_id: str) -> IngestionStatusResponse:
    db_record = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.celery_task_id == task_id, DocumentRecord.tenant_id == principal.tenant_id)
        .first()
    )
    if db_record is None:
        raise NotFoundError(f"No ingestion task found with task_id={task_id}.")

    celery_result = celery_app.AsyncResult(task_id)

    # Only populated if the worker itself reported a percentage via
    # update_state(meta={"progress_percent": ...}) — never fabricated here.
    progress_percent = None
    if isinstance(celery_result.info, dict):
        progress_percent = celery_result.info.get("progress_percent")

    return IngestionStatusResponse(
        task_id=task_id,
        document_id=db_record.id,
        status=db_record.status,
        stage=db_record.status if db_record.status in _KNOWN_STAGES else None,
        progress_percent=progress_percent,
        error=db_record.error_message,
    )
