#!/usr/bin/env bash
# Backs up PostgreSQL (pg_dump), Qdrant (collection snapshot) and MinIO
# (bucket mirror) to timestamped files under ./backups/. Run from the
# repository root, with the prod stack already up:
#   ./deployment/scripts/backup.sh
#
# Redis is deliberately NOT backed up here: its only persistent role in this
# app is the Celery broker/result backend (src/core/config.py's
# celery_broker_url) plus the exact-match chat response cache
# (src/core/cache.py) — both are disposable. Losing them means in-flight
# Celery tasks are lost and the chat cache is cold, not data loss; redis's
# own AOF file (appendonly.aof, enabled in docker-compose.prod.yml) already
# protects against a plain container restart. If you add anything
# Redis-resident that must survive a full data-center loss, back up the named
# `redis_data` volume too (see restore.sh's "Docker volumes are not backups"
# note — the same applies here).
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-deployment/compose/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_ROOT="${BACKUP_ROOT:-backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found." >&2
    exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
: "${POSTGRES_USER:?}"; : "${POSTGRES_DB:?}"
: "${QDRANT_COLLECTION:?}"
: "${MINIO_ROOT_USER:?}"; : "${MINIO_ROOT_PASSWORD:?}"; : "${MINIO_BUCKET:=rag-documents}"

COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")
PROJECT_NAME="$("${COMPOSE[@]}" config --format json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('name','rag-prod'))" 2>/dev/null || echo rag-prod)"

mkdir -p "$BACKUP_DIR"
echo "Backing up to $BACKUP_DIR"

# --- PostgreSQL ---
echo "[1/3] PostgreSQL (pg_dump, custom format)..."
"${COMPOSE[@]}" exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
    > "$BACKUP_DIR/postgres_${POSTGRES_DB}_${TIMESTAMP}.dump"
echo "    -> $BACKUP_DIR/postgres_${POSTGRES_DB}_${TIMESTAMP}.dump"

# --- Qdrant ---
# Snapshots preserve both the collection's vector/payload data AND its
# configuration (distance metric, named-vector schema) — a full restore
# target, not just raw vectors.
echo "[2/3] Qdrant (collection snapshot: $QDRANT_COLLECTION)..."
SNAPSHOT_RESPONSE="$("${COMPOSE[@]}" exec -T qdrant curl -s -X POST \
    "http://localhost:6333/collections/$QDRANT_COLLECTION/snapshots")"
SNAPSHOT_NAME="$(echo "$SNAPSHOT_RESPONSE" | grep -oE '"name"[[:space:]]*:[[:space:]]*"[^"]+"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')"
if [ -z "$SNAPSHOT_NAME" ]; then
    echo "    Failed to create Qdrant snapshot. Response: $SNAPSHOT_RESPONSE" >&2
    exit 1
fi
"${COMPOSE[@]}" exec -T qdrant curl -s \
    "http://localhost:6333/collections/$QDRANT_COLLECTION/snapshots/$SNAPSHOT_NAME" \
    -o "/tmp/$SNAPSHOT_NAME"
"${COMPOSE[@]}" cp "qdrant:/tmp/$SNAPSHOT_NAME" "$BACKUP_DIR/qdrant_${QDRANT_COLLECTION}_${TIMESTAMP}.snapshot"
"${COMPOSE[@]}" exec -T qdrant rm -f "/tmp/$SNAPSHOT_NAME"
echo "    -> $BACKUP_DIR/qdrant_${QDRANT_COLLECTION}_${TIMESTAMP}.snapshot"

# --- MinIO ---
echo "[3/3] MinIO (mirroring bucket: $MINIO_BUCKET)..."
mkdir -p "$BACKUP_DIR/minio_${MINIO_BUCKET}"
docker run --rm \
    --network "${PROJECT_NAME}_backend_net" \
    -v "$(pwd)/$BACKUP_DIR/minio_${MINIO_BUCKET}:/backup" \
    --entrypoint sh \
    minio/mc:latest -c "
        mc alias set local http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' &&
        mc mirror --overwrite local/$MINIO_BUCKET /backup
    "
echo "    -> $BACKUP_DIR/minio_${MINIO_BUCKET}/"

echo ""
echo "Backup complete: $BACKUP_DIR"
echo "Restore with: ./deployment/scripts/restore.sh $BACKUP_DIR"
