import asyncio
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor

from celery.utils.log import get_task_logger

from src.core.db import DocumentRecord, ParentChunkRecord, SessionLocal
from src.core.storage import download_document
from src.ingestion.chunking import chunk_document
from src.ingestion.embeddings import embed_chunks
from src.ingestion.parsers import DocumentParsingError, parse_pdf
from src.ingestion.worker import celery_app
from src.models.okf import DocumentMetadata, DocumentType
from src.retrieval.qdrant_client import UPSERT_BATCH_SIZE, delete_chunks_by_document, upsert_chunks_batch

logger = get_task_logger(__name__)

MAX_RETRIES = 3


def _run_coroutine_sync(coro):
    """Runs an async coroutine from sync code, whether or not the calling
    thread already has a running event loop.

    A real Celery worker process has no event loop, so `asyncio.run()` alone
    would be fine - but with CELERY_TASK_ALWAYS_EAGER (free-tier deploys
    with no separate worker, see src/ingestion/worker.py), this task runs
    inline inside FastAPI's own async request handler, which already has one
    running. Calling asyncio.run() there raises "asyncio.run() cannot be
    called from a running event loop" on every single call - deterministic,
    not transient, so Celery's autoretry only burns through retries hitting
    the same error each time. A fresh thread never has a running loop, so
    this works identically in both cases.
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


@celery_app.task(
    name="ingestion.ingest_document_task",
    bind=True,
    max_retries=MAX_RETRIES,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def ingest_document_task(self, document_id: str) -> dict:
    """Parse, chunk, embed and index a document whose DocumentRecord was already
    created by the API (status='queued'). Fetches the original file from MinIO.

    Retries up to MAX_RETRIES times with exponential backoff (celery's
    retry_backoff) on any exception — transient Qdrant/Postgres/IO failures
    included. On retry, any chunks already upserted for this document are
    deleted first so re-running the task never leaves duplicate vectors.
    """
    doc_uuid = uuid.UUID(document_id)

    db = SessionLocal()
    try:
        db_record = db.get(DocumentRecord, doc_uuid)
        if db_record is None:
            logger.error("ingest_document_task: no DocumentRecord found for id=%s", document_id)
            return {"document_id": document_id, "status": "failed", "error": "document record not found"}

        if self.request.retries > 0:
            delete_chunks_by_document(document_id)
            db.query(ParentChunkRecord).filter(ParentChunkRecord.document_id == doc_uuid).delete()
            db.commit()

        metadata = DocumentMetadata(
            document_id=doc_uuid,
            tenant_id=db_record.tenant_id,
            source_uri=db_record.source_uri,
            document_type=DocumentType(db_record.document_type),
            author=db_record.author,
        )

        db_record.status = "parsing"
        db.commit()

        tmp_path = None
        try:
            file_bytes = download_document(db_record.storage_path)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name

            try:
                parsed = _run_coroutine_sync(parse_pdf(tmp_path))
                # A scanned/image-only PDF parses "successfully" (no exception)
                # but yields no text at all — without this check it would
                # silently end up "indexed" with zero chunks and nothing ever
                # retrievable, giving no indication anything went wrong.
                if not any(page.text.strip() for page in parsed.pages):
                    raise DocumentParsingError(
                        "No extractable text found in this PDF — it may be a scanned or "
                        "image-only document. OCR is not currently supported; try a PDF "
                        "with a text layer."
                    )
            except DocumentParsingError as exc:
                db_record.status = "failed"
                db_record.error_message = str(exc)
                db.commit()
                raise
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        metadata.page_numbers = [page.page_number for page in parsed.pages]

        db_record.status = "chunking"
        db.commit()
        parent_chunks, child_chunks = chunk_document(parsed, metadata)

        db_record.status = "embedding"
        db.commit()
        child_chunks = embed_chunks(child_chunks)

        upserted_count = upsert_chunks_batch(child_chunks, batch_size=UPSERT_BATCH_SIZE)

        for parent in parent_chunks:
            db.add(
                ParentChunkRecord(
                    id=parent.parent_id,
                    document_id=parent.document_id,
                    chunk_index=parent.chunk_index,
                    content=parent.content,
                    page_numbers=parent.page_numbers,
                    token_count=parent.token_count,
                )
            )

        db_record.status = "indexed"
        db_record.error_message = None
        db.commit()

        logger.info(
            "Ingested document %s: %d parent chunks, %d child chunks upserted",
            document_id,
            len(parent_chunks),
            upserted_count,
        )
        return {
            "document_id": document_id,
            "status": "indexed",
            "parent_chunk_count": len(parent_chunks),
            "child_chunk_count": upserted_count,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "Ingestion failed for document_id=%s (attempt %d/%d): %s",
            document_id,
            self.request.retries + 1,
            MAX_RETRIES + 1,
            exc,
            exc_info=True,
        )
        raise
    finally:
        db.close()
