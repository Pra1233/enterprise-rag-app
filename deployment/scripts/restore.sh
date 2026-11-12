#!/usr/bin/env bash
# Restores PostgreSQL, Qdrant and MinIO from a backup directory produced by
# backup.sh. Run from the repository root, with the prod stack already up:
#   ./deployment/scripts/restore.sh backups/20260101T000000Z
#
# DESTRUCTIVE: this overwrites the current database/collection/bucket
# contents. Confirms before each step.
set -euo pipefail

BACKUP_DIR="${1:?Usage: restore.sh <backup-directory>}"
COMPOSE_FILE="${COMPOSE_FILE:-deployment/compose/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: backup directory '$BACKUP_DIR' not found." >&2
    exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
: "${POSTGRES_USER:?}"; : "${POSTGRES_DB:?}"
: "${QDRANT_COLLECTION:?}"
: "${MINIO_ROOT_USER:?}"; : "${MINIO_ROOT_PASSWORD:?}"; : "${MINIO_BUCKET:=rag-documents}"

COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")
PROJECT_NAME="$("${COMPOSE[@]}" config --format json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('name','rag-prod'))" 2>/dev/null || echo rag-prod)"

confirm() {
    read -r -p "$1 [y/N] " reply
    [ "$reply" = "y" ] || [ "$reply" = "Y" ]
}

# --- PostgreSQL ---
PG_DUMP_FILE=$(find "$BACKUP_DIR" -maxdepth 1 -name 'postgres_*.dump' | head -1)
if [ -n "$PG_DUMP_FILE" ] && confirm "Restore PostgreSQL from $PG_DUMP_FILE? This REPLACES current data."; then
    echo "Restoring PostgreSQL..."
    "${COMPOSE[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
        < "$PG_DUMP_FILE"
    echo "    PostgreSQL restored."
else
    echo "    Skipped PostgreSQL."
fi

# --- Qdrant ---
QDRANT_SNAPSHOT=$(find "$BACKUP_DIR" -maxdepth 1 -name 'qdrant_*.snapshot' | head -1)
if [ -n "$QDRANT_SNAPSHOT" ] && confirm "Restore Qdrant collection '$QDRANT_COLLECTION' from $QDRANT_SNAPSHOT? This REPLACES the current collection."; then
    echo "Restoring Qdrant..."
    SNAPSHOT_BASENAME="$(basename "$QDRANT_SNAPSHOT")"
    "${COMPOSE[@]}" cp "$QDRANT_SNAPSHOT" "qdrant:/tmp/$SNAPSHOT_BASENAME"
    "${COMPOSE[@]}" exec -T qdrant curl -s -X POST \
        "http://localhost:6333/collections/$QDRANT_COLLECTION/snapshots/upload?priority=snapshot" \
        -F "snapshot=@/tmp/$SNAPSHOT_BASENAME"
    "${COMPOSE[@]}" exec -T qdrant rm -f "/tmp/$SNAPSHOT_BASENAME"
    echo "    Qdrant collection restored."
else
    echo "    Skipped Qdrant."
fi

# --- MinIO ---
MINIO_BACKUP_DIR=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name 'minio_*' | head -1)
if [ -n "$MINIO_BACKUP_DIR" ] && confirm "Restore MinIO bucket '$MINIO_BUCKET' from $MINIO_BACKUP_DIR? This overwrites existing objects with the same keys."; then
    echo "Restoring MinIO..."
    docker run --rm \
        --network "${PROJECT_NAME}_backend_net" \
        -v "$(pwd)/$MINIO_BACKUP_DIR:/backup:ro" \
        --entrypoint sh \
        minio/mc:latest -c "
            mc alias set local http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' &&
            mc mirror --overwrite /backup local/$MINIO_BUCKET
        "
    echo "    MinIO bucket restored."
else
    echo "    Skipped MinIO."
fi

echo ""
echo "Restore from $BACKUP_DIR complete."
echo "Restart the backend/worker services so any in-process caches pick up the restored state:"
echo "  docker compose -f $COMPOSE_FILE --env-file $ENV_FILE restart backend worker"
