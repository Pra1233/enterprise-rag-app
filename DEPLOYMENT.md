# Deployment Guide

## Architecture overview

```
                         ┌─────────────────────────┐
  Internet ── :80/:443 ─▶│  frontend (nginx)        │
                         │  - serves React build    │
                         │  - proxies /api/ ────────┼──┐
                         └─────────────────────────┘  │
                                                        ▼
                         ┌─────────────────────────────────┐
                         │  backend (FastAPI/uvicorn) :8000 │
                         └───┬───────┬───────┬───────┬──────┘
                             │       │       │       │
                      ┌──────▼─┐ ┌───▼───┐ ┌─▼────┐ ┌▼─────┐
                      │postgres│ │ redis │ │qdrant│ │minio │
                      └────────┘ └───┬───┘ └──────┘ └──────┘
                                     │ (broker)
                             ┌───────▼────────┐
                             │ worker (Celery) │── also talks to postgres/qdrant/minio
                             └─────────────────┘
```

Two Docker networks (see `deployment/compose/docker-compose.prod.yml`):
- **`backend_net`**: postgres, redis, qdrant, minio, backend, worker — none of the backing services publish a host port; they're reachable only by service name, from containers on this network.
- **`frontend_net`**: frontend (nginx) ↔ backend only, so nginx can proxy `/api/` without being able to reach postgres/redis/qdrant/minio directly.

The frontend is a static React build served by nginx, which also acts as the reverse proxy for `/api/` — there is no separate reverse-proxy container. One built frontend image works across environments via a runtime config file (`env-config.js`, regenerated from `API_BASE_URL` at container startup — see `src/config.ts`), not baked in at build time.

## Prerequisites

- Docker Engine 24+ and the Docker Compose plugin (`docker compose version`)
- A Groq API key (free, no credit card — console.groq.com)
- For production: a domain pointed at your server (for TLS) and SSH access to that server

## Development setup

```bash
cp .env.development.example .env.development
# fill in GROQ_API_KEY at minimum
```

```bash
docker compose -f deployment/compose/docker-compose.dev.yml --env-file .env.development up
```

This gives you:
- Backend on `http://localhost:8000` with `--reload` (bind-mounted `backend/src`)
- Frontend on `http://localhost:5173` (Vite dev server with HMR)
- Postgres on `localhost:5432`, Redis on `6379`, Qdrant on `6333`, MinIO on `9000`/`9001` — all exposed for local tooling (psql, redis-cli, a MinIO console, etc.). **This is dev-only** — the prod compose file never does this.

Create the schema (first run only):
```bash
docker compose -f deployment/compose/docker-compose.dev.yml --env-file .env.development exec backend \
  alembic upgrade head
```

## Production setup

```bash
cp .env.production.example .env
# fill in every MANDATORY variable (see the file's own comments):
# JWT_SECRET_KEY, GROQ_API_KEY, POSTGRES_USER, POSTGRES_PASSWORD,
# MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, FRONTEND_URL
```

```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env build
```

```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env up -d \
  postgres redis qdrant minio
```

Wait for them healthy (`docker compose ... ps`), then run the one-off migration job and bootstrap MinIO:
```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env run --rm migrate
./deployment/scripts/init-minio.sh
```

Start the application services:
```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env up -d backend worker frontend
```

Verify:
```bash
curl http://localhost/health
```

## Environment variable reference

See `.env.production.example` for the authoritative, commented list. Summary:

| Variable | Required | Notes |
|---|---|---|
| `JWT_SECRET_KEY` | **yes** | HS256 signing secret. No real login endpoint exists yet — see `src/api/dependencies.py`; mint dev tokens with the snippet in that file's docstring. |
| `GROQ_API_KEY` | **yes** | Free tier, console.groq.com |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | **yes** | Bootstraps the postgres container AND is embedded in `POSTGRES_URL` |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | **yes** | Bootstraps minio AND is embedded in `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` |
| `FRONTEND_URL` | **yes** (prod) | Backend's CORS allowlist — must be your real deployed frontend origin |
| `GROQ_MODEL` | no | Default `openai/gpt-oss-120b` — Groq's lineup changes; check `console.groq.com/docs/models` |
| `QDRANT_URL`, `REDIS_URL` | no | Default to the compose service names (`qdrant`, `redis`) |
| `CACHE_ENABLED`, `CACHE_TTL` | no | Chat response cache |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` | no | Free tier tracing, off by default |
| `EVALUATION_*` | no | Phase 6 RAGAS evaluation config |
| `CELERY_CONCURRENCY`, `CELERY_TASK_SOFT_TIME_LIMIT`, `CELERY_TASK_TIME_LIMIT` | no | Worker tuning |
| `IMAGE_TAG` | no | Set by CI on deploy; `latest` for manual use |
| `HTTP_PORT` | no | Host port nginx publishes (default 80) |
| `PUBLIC_API_BASE_URL` | no | What the frontend calls at runtime (default `/api/v1`, relative — works because nginx proxies same-origin) |

Frontend-only build var (`frontend/.env.example`): `VITE_API_BASE_URL` — only used as a fallback for local `npm run dev`; in Docker, `API_BASE_URL` (container env) overrides it at startup via `env-config.js`.

## Docker commands

```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env ps
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env logs -f backend
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env restart worker
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env down
```

```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env build backend worker
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env up -d backend worker
```

## Database migration commands

Migrations are Alembic, under `backend/alembic/`. They never run automatically inside the backend/worker containers — only via the dedicated `migrate` one-off job (`profiles: ["migrate"]` in the compose file), so a multi-replica deployment never races multiple containers trying to migrate at once.

```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env run --rm migrate
```

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
```

```bash
docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env run --rm migrate \
  alembic downgrade -1
```

## Backup and restoration

```bash
./deployment/scripts/backup.sh
```

Writes `backups/<UTC-timestamp>/` containing a Postgres `pg_dump` (custom format), a Qdrant collection snapshot, and a MinIO bucket mirror. **Docker named volumes are not backups** — a `docker volume rm` or host disk failure takes the volume with it; `backup.sh`'s output is a portable, independently-restorable copy.

```bash
./deployment/scripts/restore.sh backups/20260101T000000Z
```

Prompts for confirmation before touching each of Postgres/Qdrant/MinIO — restores are destructive (they replace current data).

Redis is deliberately not included: it only holds the Celery broker/result backend and the disposable chat cache — see the comment at the top of `backup.sh` for the full reasoning.

## SSL configuration

The tested `docker-compose.prod.yml` + `deployment/nginx/default.conf` serve plain HTTP — this repo has no real domain to provision a certificate against, so HTTPS itself is **documented, not tested**, here.

To enable it with a real domain, using Certbot (free, Let's Encrypt):

1. Point your domain's DNS A record at the server.
2. Add a `certbot` service to the compose file (image `certbot/certbot`), sharing a volume with nginx for `/var/www/certbot` (ACME challenge) and `/etc/letsencrypt` (certs).
3. Swap `deployment/nginx/default.conf` for `deployment/nginx/default.ssl.conf.template` (substitute `${DOMAIN}`), which redirects HTTP→HTTPS and terminates TLS.
4. Run once to obtain the initial cert:
   ```bash
   docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env run --rm certbot \
     certonly --webroot -w /var/www/certbot -d your-domain.example.com
   ```
5. Reload nginx: `docker compose ... exec frontend nginx -s reload`
6. Certbot auto-renews via its container's built-in cron; reload nginx after renewal (a `deploy-hook` in the certbot invocation, or a small cron job calling `nginx -s reload`).

Never commit `/etc/letsencrypt` or any private key to the repository.

## CI/CD workflow

- **`.github/workflows/ci.yml`** — runs on every PR and push to `main`: backend lint/format (`ruff`)/tests, frontend typecheck/lint/tests/build, then builds both Docker images and scans them with Trivy (report-only by default — flip `exit-code` to `"1"` once you've triaged a baseline).
- **`.github/workflows/deploy.yml`** — triggered by a successful CI run on `main` (or manually via `workflow_dispatch`, which also doubles as the rollback path — see below). Builds and pushes both images to GHCR tagged with the commit SHA **and** `latest`, SSHes to the deployment server, pulls the new images, runs the migration job, recreates the application services, then polls `/health` for up to 60s before declaring success.

Required GitHub Actions secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH` (the directory on the server holding this repo + its `.env`). `GITHUB_TOKEN` (built-in) handles GHCR auth — no extra registry secret needed.

**Not tested in this sandbox** — there's no real deployment server or domain here. The SSH/remote steps are a correct, reviewed reference implementation, not a verified one; test them against a real server before relying on them.

## Rollback instructions

Every successful `deploy.yml` run pushes images tagged with that commit's short SHA (never only `latest`), so a previous release's images stay in GHCR indefinitely.

To roll back: Actions → Deploy → **Run workflow**, set `image_tag` to the last known-good SHA (visible in a previous run's summary), run. This skips the build step entirely and redeploys the existing image — it still runs the migration job and health check, so a rollback that would leave the DB schema ahead of the code is caught the same way a forward deploy is.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker compose up` fails immediately citing a missing variable | A mandatory `.env` var is empty | Check `.env.production.example`'s "mandatory" list |
| `backend`/`worker` unhealthy, logs show DB connection errors | `migrate` job never ran, or Postgres isn't healthy yet | `docker compose ... run --rm migrate`; check `docker compose ... ps postgres` |
| Chat responses don't stream, arrive all at once | A proxy/CDN in front of nginx is buffering | Confirm `proxy_buffering off` reached the actual response — some CDNs re-buffer regardless; bypass or configure it to pass SSE through |
| 413 on document upload | nginx's `client_max_body_size` (55m) or the backend's 50MB cap was exceeded | Expected for files >50MB — the backend's limit is intentional (`src/core/config.py`) |
| Frontend loads but all API calls fail | `API_BASE_URL` / `PUBLIC_API_BASE_URL` mismatch, or CORS | Check `env-config.js` in the browser (should show the real API URL); check `FRONTEND_URL` matches the frontend's actual origin |
| Groq calls fail with 404 on the model name | Groq retired the configured model | Check `console.groq.com/docs/models`, update `GROQ_MODEL` |

## Monitoring and maintenance

- `GET /health` — liveness only. `GET /health/ready` — checks Postgres connectivity.
- `src/observability/metrics.py`'s in-process `MetricsRegistry` tracks API/RAG-stage/ingestion/LLM metrics; `.snapshot()` returns a JSON-serializable dict (not yet exposed as an HTTP endpoint — a natural follow-up).
- LangSmith tracing (`LANGSMITH_TRACING=true`) gives per-request traces of the whole RAG pipeline, free up to 50k traces/month.
- Regular dependency updates: `requirements.txt` and `frontend/package-lock.json` are both pinned; Dependabot or a scheduled CI job bumping them + re-running the full test suite is a reasonable follow-up, not yet configured.
- Disk growth to watch: `postgres_data`, `qdrant_data`, `minio_data` volumes grow with your document corpus — no automatic pruning is configured.

## Three deployment options

### Option A: VPS / Azure VM with Docker Compose (what's actually tested here)

1. Provision a VM (2 vCPU / 4GB RAM minimum — embeddings/reranking run on CPU).
2. Install Docker Engine + Compose plugin (`curl -fsSL https://get.docker.com | sh`).
3. Firewall: allow 22 (SSH), 80, 443 only. Everything else (Postgres, Redis, Qdrant, MinIO) stays off the public interface entirely — the compose file never publishes those ports.
4. Point your domain's A record at the VM's IP.
5. `git clone` this repo, `cp .env.production.example .env`, fill in secrets.
6. `docker compose -f deployment/compose/docker-compose.prod.yml --env-file .env up -d`, run the migration job, run `init-minio.sh`.
7. Set up Certbot per the SSL section above.
8. Schedule `backup.sh` via cron (e.g. nightly), store the `backups/` output off-box (rsync to another host, or an object store).

Simplest option, full control, single point of failure (one VM).

### Option B: Cloud-managed infrastructure

Moving each backing service to a managed equivalent, one at a time, without changing application code (the backend only knows `POSTGRES_URL`/`REDIS_URL`/`QDRANT_URL`/`MINIO_*`, not how those are hosted):

- **Managed PostgreSQL** (RDS, Cloud SQL, Azure Database for PostgreSQL): point `POSTGRES_URL` at it; drop the `postgres` service and its volume from compose.
- **Managed Redis** (ElastiCache, Memorystore, Azure Cache for Redis): point `REDIS_URL` at it; drop the `redis` service. Note the maxmemory/eviction policy configured in `docker-compose.prod.yml`'s `redis` service becomes the managed service's own setting instead.
- **Cloud object storage** (S3, GCS, Azure Blob): `src/core/storage.py` uses the `minio` Python SDK, which is S3-API-compatible — pointing `MINIO_ENDPOINT` at a real S3-compatible endpoint (or swapping to `boto3` if you need native, non-S3-compatible object storage) replaces the `minio` service.
- **Qdrant**: Qdrant Cloud (the project's own managed offering) is the direct equivalent — point `QDRANT_URL` at it.
- **Dedicated application containers**: backend/worker/frontend move to ECS/Cloud Run/Container Apps/AKS — the same images this repo builds, just orchestrated differently; the Dockerfiles don't change.
- **Managed monitoring**: CloudWatch/Cloud Monitoring/Application Insights replace ad-hoc `docker compose logs`; `src/observability/metrics.py`'s registry would need a push/scrape exporter added (it's designed to be adaptable to this — see its module docstring).

This is the lowest-maintenance path at the cost of per-service cloud bills instead of one VM's flat cost.

### Option C: Split frontend and backend

- **Frontend**: deploy the Vite build (not the nginx container) to a static host (Cloudflare Pages, Netlify, Vercel, S3+CloudFront). Build-time env (`VITE_API_BASE_URL`) or the same runtime `env-config.js` mechanism (served as a static file alongside the build) both work.
- **Backend + Celery**: run on a VM or container platform (ECS, Cloud Run — note Cloud Run's request-based model doesn't suit a long-lived Celery worker well; a VM or a platform with persistent background workers, like ECS, fits better).
- **Networking/CORS**: the frontend now calls the backend cross-origin. Set `FRONTEND_URL` to the frontend's real origin (CORS allowlist in `src/api/main.py`); `PUBLIC_API_BASE_URL` becomes the full backend URL (`https://api.your-domain.example.com/api/v1`), not a relative path, since there's no shared nginx to make it same-origin.
- **Secure API communication**: the backend's existing JWT auth (`src/api/dependencies.py`) and HTTPS on the backend's own public endpoint remain the security boundary — no additional mechanism needed, just make sure the backend itself has a cert (its own Certbot/managed-cert setup if directly public, or sits behind a cloud load balancer that terminates TLS).

Not every static host offers free persistent background workers or unlimited compute — confirm your chosen backend host's pricing model covers Celery's always-on nature before committing to this split.

## Deployment testing checklist

See the completion summary message for this phase — I ran the actual stack in this environment and report real pass/fail/not-applicable results there, not an assumed checklist.
