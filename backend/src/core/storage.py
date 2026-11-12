import io
import logging
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from src.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_minio_client() -> Minio:
    """Cached, process-wide MinIO (S3-compatible) client."""
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> None:
    """Create the documents bucket if it doesn't exist yet. Idempotent."""
    settings = get_settings()
    client = get_minio_client()
    try:
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
            logger.info("Created MinIO bucket '%s'", settings.minio_bucket)
    except S3Error:
        logger.error("Failed to ensure MinIO bucket '%s' exists", settings.minio_bucket, exc_info=True)
        raise


def upload_document(object_key: str, data: bytes, content_type: str) -> None:
    """Upload raw document bytes to the documents bucket under object_key."""
    settings = get_settings()
    client = get_minio_client()
    client.put_object(
        settings.minio_bucket,
        object_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_document(object_key: str) -> bytes:
    """Download raw document bytes from the documents bucket."""
    settings = get_settings()
    client = get_minio_client()
    response = client.get_object(settings.minio_bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_document(object_key: str) -> None:
    """Delete an object from the documents bucket. Idempotent — missing keys are not an error."""
    settings = get_settings()
    client = get_minio_client()
    try:
        client.remove_object(settings.minio_bucket, object_key)
    except S3Error as exc:
        if exc.code != "NoSuchKey":
            raise
