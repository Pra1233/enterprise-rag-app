# Multi-stage build for the FastAPI backend. The same image is used for the
# Celery worker service too (see deployment/compose/docker-compose.prod.yml) —
# only the container `command` differs, so the two never duplicate the build.
#
# Build context must be the `backend/` directory:
#   docker build -f deployment/docker/backend.Dockerfile backend/

# Python 3.13, not 3.11: under 3.11/3.10, langchain-community==0.3.14 pins
# numpy<2 while pandas==3.1.1 (Phase 6) requires numpy>=2.0.2 — a genuine,
# unresolvable conflict caught by actually building this image. Under 3.12+,
# langchain-community's numpy<2 pin is python-version-gated and doesn't apply,
# so the two coexist. This also matches the Python version the whole backend
# has actually been developed and tested against in this project so far.

# --- Stage 1: build dependencies (compilers only live here) ---
FROM python:3.13-slim AS builder

# Optional build-time proxy for apt/pip — empty by default (a no-op for any
# normal build environment with direct internet access). Only needed when
# building inside a network-restricted sandbox; never baked into the final
# image since these ARGs aren't referenced in the runtime stage at all.
ARG HTTP_PROXY=
ARG HTTPS_PROXY=

WORKDIR /build

# The https:// rewrite only runs when a proxy is actually supplied (some
# forward proxies only tunnel HTTPS/CONNECT, not plain HTTP) — a no-op for a
# normal build with direct internet access, where http:// works fine as-is.
RUN if [ -n "${HTTPS_PROXY}" ]; then sed -i 's#http://#https://#g' /etc/apt/sources.list.d/*.sources 2>/dev/null || sed -i 's#http://#https://#g' /etc/apt/sources.list; fi \
    && http_proxy="${HTTP_PROXY}" https_proxy="${HTTPS_PROXY}" apt-get update \
    && http_proxy="${HTTP_PROXY}" https_proxy="${HTTPS_PROXY}" apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# --extra-index-url pulls PyTorch's CPU-only wheels instead of the default
# CUDA build — this app only ever runs embeddings/reranking on CPU
# (EMBEDDING_DEVICE=cpu in src/core/config.py), so the GPU build's several
# extra GB of bundled NVIDIA libraries (cuBLAS, cuDNN, nccl, triton, ...)
# are pure waste here. Found by actually building this image: the GPU
# build pushed the image well past 10GB and exhausted local disk.
RUN http_proxy="${HTTP_PROXY}" https_proxy="${HTTPS_PROXY}" pip install --no-cache-dir --upgrade pip \
    && http_proxy="${HTTP_PROXY}" https_proxy="${HTTPS_PROXY}" pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt

# --- Stage 2: runtime (no compilers, no build cache, non-root) ---
FROM python:3.13-slim AS runtime

ARG HTTP_PROXY=
ARG HTTPS_PROXY=

# libpq5: psycopg2 runtime; libgomp1: required by torch (sentence-transformers'
# backend) at import time; tini: PID 1 init so SIGTERM reaches uvicorn cleanly
# and zombie processes from subprocess calls are reaped.
RUN if [ -n "${HTTPS_PROXY}" ]; then sed -i 's#http://#https://#g' /etc/apt/sources.list.d/*.sources 2>/dev/null || sed -i 's#http://#https://#g' /etc/apt/sources.list; fi \
    && http_proxy="${HTTP_PROXY}" https_proxy="${HTTPS_PROXY}" apt-get update \
    && http_proxy="${HTTP_PROXY}" https_proxy="${HTTPS_PROXY}" apt-get install -y --no-install-recommends libpq5 libgomp1 tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Only the application source and migration files — never .env, .git, test
# fixtures, etc. (enforced by .dockerignore alongside this file's build context).
# alembic.ini + alembic/ are needed so the one-off migration job (see
# docker-compose.prod.yml's `migrate` service) can run inside this same image.
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser start-web-and-worker.sh ./start-web-and-worker.sh
RUN chmod +x ./start-web-and-worker.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# tini as PID 1 forwards SIGTERM to uvicorn so in-flight requests get uvicorn's
# own graceful-shutdown handling instead of being hard-killed by the engine.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
