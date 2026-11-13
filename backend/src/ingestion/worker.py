from celery import Celery

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ingestion_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.ingestion.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    # Named "ingestion" queue (rather than Celery's implicit default "celery"
    # queue) so a worker fleet can dedicate concurrency/resources to document
    # processing specifically, and so a future task type (e.g. a lighter
    # "notifications" queue) can run on separate, differently-sized workers
    # without competing with ingestion jobs for the same pool.
    task_default_queue="ingestion",
    task_routes={
        "ingestion.ingest_document_task": {"queue": "ingestion"},
    },
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)
