# RAG Console

An enterprise-style Retrieval-Augmented Generation (RAG) application: upload PDFs, ask questions in natural language, and get answers grounded in your own documents with cited sources. Built with a real auth system, role-based access control, an admin panel, and per-user usage quotas — not a toy chatbot demo.

**Live demo:** _add your deployed URL here_
**Demo login:** `demo_user` / `demo123` (or use the one-click "Continue as Demo User" button)

---

## Why this project

Most RAG tutorials stop at "upload a PDF, ask a question." This one goes further, covering the parts that make a RAG system actually usable by more than one person:

- **Real authentication** — username/password login issuing short-lived JWTs, not a pasted dev token
- **Role-based access control** — `admin` vs `user` roles, enforced server-side on every protected route
- **Per-user quotas** — admins set chat-message and upload limits per user; enforced atomically at the database level (race-condition-safe) before any Groq/Celery work happens
- **Admin panel** — create/manage users, adjust quotas, and view a live login audit log
- **Async ingestion pipeline** — uploads return immediately; parsing, chunking, embedding, and indexing happen in a Celery worker, with live status polling in the UI
- **Hybrid retrieval** — dense + sparse (BM25-style) vector search in Qdrant, followed by a cross-encoder reranking pass, followed by a relevance-grading step that triggers query rewriting before falling back to a clear "nothing relevant found" response instead of hallucinating

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────────────┐
│  React SPA  │─────▶│  FastAPI API │─────▶│  Groq (LLM inference)   │
│  (Vite)     │ SSE  │              │      └─────────────────────────┘
└─────────────┘      │              │      ┌─────────────────────────┐
                      │              │─────▶│  Qdrant (vector search) │
                      │              │      └─────────────────────────┘
                      │              │      ┌─────────────────────────┐
                      │              │─────▶│  PostgreSQL (users,     │
                      │              │      │  documents, audit log)  │
                      └──────┬───────┘      └─────────────────────────┘
                             │ enqueue
                             ▼
                      ┌──────────────┐      ┌─────────────────────────┐
                      │ Celery worker│─────▶│  MinIO (object storage) │
                      │ (ingestion)  │      └─────────────────────────┘
                      └──────────────┘
                             ▲
                             │ broker
                      ┌──────────────┐
                      │    Redis     │
                      └──────────────┘
```

Full production deployment architecture (Docker Compose, nginx reverse proxy, network isolation) is documented in [DEPLOYMENT.md](DEPLOYMENT.md).

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, Radix UI, Framer Motion |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic |
| Auth | JWT (HS256) + Argon2 password hashing |
| LLM | Groq (free tier) via LangChain / LangGraph |
| Vector DB | Qdrant (dense + sparse hybrid search) |
| Relational DB | PostgreSQL |
| Object storage | MinIO (S3-compatible) |
| Task queue | Celery + Redis |
| Observability | LangSmith tracing (optional) |

## Key features in detail

- **Chat** — streaming (SSE) responses token-by-token, with inline citations linking back to source document chunks, response caching for repeated queries, and a conversation list that auto-names itself from your first question (like ChatGPT)
- **Documents** — drag-and-drop PDF upload with live ingestion progress (queued → parsing → chunking → embedding → indexed), reprocessing, and deletion
- **Admin panel** — user management (create/edit/deactivate, set quotas) and a paginated login audit log showing who logged in, when, and their current usage
- **Mobile-first UI** — collapsible sidebar + bottom tab bar, dark/light mode, glassmorphism design accents

## Local development

Requires Docker Desktop, Python 3.13, and Node 22. On Windows, a one-command startup script is included:

```powershell
.\start-dev.ps1
```

This starts Docker infra (Postgres/Redis/Qdrant/MinIO), then the backend, Celery worker, and frontend dev server each in their own window. Stop infra with `.\stop-dev.ps1`.

**First-time setup** (after cloning, before the first run):

```bash
# 1. Copy env templates and fill in your own values (Groq API key, JWT secret, etc.)
cp .env.development.example .env.development
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 2. Backend: create venv, install deps, migrate, seed initial users
cd backend
python -m venv .venv
.venv\Scripts\activate          # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
alembic upgrade head
$env:ADMIN_PASSWORD = "your-choice"   # PowerShell; use `export` on bash
python -m src.scripts.seed_users

# 3. Frontend: install deps
cd ../frontend
npm ci
```

Then run `.\start-dev.ps1` (Windows) or start each service manually — see the script for the exact commands on other platforms.

Once running: `http://localhost:5173` (app), `http://localhost:8000/docs` (API docs).

## Project structure

```
backend/
  src/
    api/          FastAPI routes, request/response schemas, dependencies
    core/          config, DB models, security (hashing/JWT), exceptions
    services/       business logic (auth, admin, chat, documents, ingestion)
    ingestion/       PDF parsing, chunking, embedding, Celery tasks
    retrieval/       LangGraph RAG pipeline (retrieve -> rerank -> grade -> generate)
    scripts/         one-off ops scripts (seed_users.py)
  alembic/          database migrations
  tests/             pytest suite
frontend/
  src/
    api/            axios client + per-resource API modules
    components/       organized by feature (chat/, documents/, admin/, layout/, common/, auth/)
    context/          AuthContext
    hooks/            React Query hooks, useChat/useSSE for streaming
    pages/            route-level components
deployment/         Docker Compose files, nginx config, prod Dockerfiles
```

## License

MIT — see [LICENSE](LICENSE).
