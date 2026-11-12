import logging
import uuid

from sqlalchemy.orm import Session

from src.api.dependencies import Principal
from src.api.exceptions import ForbiddenError, NotFoundError
from src.api.schemas.documents import DeleteResponse, DocumentListResponse, DocumentOut, ReprocessResponse
from src.core.cache import ChatResponseCache
from src.core.config import get_settings
from src.core.db import DocumentRecord
from src.core.storage import delete_document as delete_from_storage
from src.ingestion.tasks import ingest_document_task
from src.retrieval.qdrant_client import delete_chunks_by_document

logger = logging.getLogger(__name__)


def _to_out(record: DocumentRecord) -> DocumentOut:
    return DocumentOut(
        document_id=record.id,
        original_filename=record.original_filename,
        document_type=record.document_type,
        author=record.author,
        status=record.status,
        error_message=record.error_message,
        file_size_bytes=record.file_size_bytes,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _get_owned_document(db: Session, principal: Principal, document_id: uuid.UUID) -> DocumentRecord:
    record = db.get(DocumentRecord, document_id)
    if record is None or record.tenant_id != principal.tenant_id:
        # 404 either way — never confirm that a document exists in another tenant.
        raise NotFoundError(f"Document {document_id} not found.")
    return record


def _authorize_mutation(principal: Principal, record: DocumentRecord) -> None:
    """Within the same tenant, only the document's owner or an admin may change it."""
    if record.owner_id != principal.user_id and "admin" not in principal.scopes:
        raise ForbiddenError("You do not have permission to modify this document.")


def list_documents(
    db: Session,
    principal: Principal,
    page: int,
    page_size: int,
    document_type: str | None,
    status: str | None,
) -> DocumentListResponse:
    query = db.query(DocumentRecord).filter(DocumentRecord.tenant_id == principal.tenant_id)
    if document_type:
        query = query.filter(DocumentRecord.document_type == document_type)
    if status:
        query = query.filter(DocumentRecord.status == status)

    total = query.count()
    records = query.order_by(DocumentRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return DocumentListResponse(items=[_to_out(r) for r in records], total=total, page=page, page_size=page_size)


def get_document(db: Session, principal: Principal, document_id: uuid.UUID) -> DocumentOut:
    return _to_out(_get_owned_document(db, principal, document_id))


def delete_document(db: Session, principal: Principal, document_id: uuid.UUID) -> DeleteResponse:
    """Delete a document consistently across Qdrant, MinIO and Postgres.

    Deletion order matters: vectors first (so a partial failure never leaves
    stale, still-queryable chunks after the document "disappears"), then the
    object store blob, then the Postgres row last — if anything fails before
    the final commit, the document record is still there and the delete is
    safe to retry rather than silently half-done.
    """
    record = _get_owned_document(db, principal, document_id)
    _authorize_mutation(principal, record)

    try:
        delete_chunks_by_document(str(document_id))
    except Exception:
        logger.error("Failed to delete Qdrant chunks for document %s", document_id, exc_info=True)
        raise

    try:
        delete_from_storage(record.storage_path)
    except Exception:
        logger.error("Failed to delete MinIO object for document %s", document_id, exc_info=True)
        raise

    db.delete(record)
    db.commit()

    ChatResponseCache(default_ttl_seconds=get_settings().cache_ttl).bump_document_version(principal.tenant_id)

    return DeleteResponse(document_id=document_id, status="deleted", message="Document deleted.")


def reprocess_document(db: Session, principal: Principal, document_id: uuid.UUID) -> ReprocessResponse:
    """Re-run ingestion for an existing document: clear its old vectors first,
    then re-enqueue the same Celery task used for first-time ingestion.
    """
    record = _get_owned_document(db, principal, document_id)
    _authorize_mutation(principal, record)

    delete_chunks_by_document(str(document_id))
    record.status = "queued"
    record.error_message = None
    db.commit()

    async_result = ingest_document_task.delay(str(document_id))
    record.celery_task_id = async_result.id
    db.commit()

    ChatResponseCache(default_ttl_seconds=get_settings().cache_ttl).bump_document_version(principal.tenant_id)

    return ReprocessResponse(
        document_id=document_id, task_id=async_result.id, status="queued", message="Reprocessing started."
    )
