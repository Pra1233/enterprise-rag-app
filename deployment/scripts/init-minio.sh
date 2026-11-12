#!/usr/bin/env bash
# One-time MinIO bootstrap: creates the documents bucket and locks it down to
# private access. The backend's own ensure_bucket() (src/core/storage.py)
# already creates the bucket lazily on first upload — this script exists for
# operators who want the bucket to exist (with an explicit, reviewable
# policy) BEFORE the application ever starts, e.g. as part of initial server
# provisioning.
#
# Usage (from the repository root, with the prod stack already up):
#   ./deployment/scripts/init-minio.sh
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-deployment/compose/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found. Copy .env.production.example to .env first." >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${MINIO_ROOT_USER:?MINIO_ROOT_USER must be set in $ENV_FILE}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD must be set in $ENV_FILE}"
: "${MINIO_BUCKET:=rag-documents}"

echo "Waiting for MinIO to be healthy..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T minio \
    sh -c 'until mc ready local 2>/dev/null; do sleep 1; done' || true

echo "Configuring mc alias and creating bucket '$MINIO_BUCKET' (private)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T minio sh -c "
    mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' &&
    mc mb --ignore-existing local/$MINIO_BUCKET &&
    mc anonymous set none local/$MINIO_BUCKET
"

echo "Done. Bucket '$MINIO_BUCKET' exists and is private (no anonymous access)."
