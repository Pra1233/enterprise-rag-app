#!/bin/sh
# Render's free tier has no Background Worker option, so the Celery worker
# runs backgrounded inside this same container, alongside uvicorn. Kept as a
# real script file (not an inline dockerCommand) since Render's Blueprint
# dockerCommand field does not reliably shell-parse `&`/quoting.
set -e

celery -A src.ingestion.worker.celery_app worker --loglevel=info --concurrency=1 &

exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
