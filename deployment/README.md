# `deployment/`

Full guide: [`../DEPLOYMENT.md`](../DEPLOYMENT.md). This file just maps the directory.

```
deployment/
├── docker/
│   ├── backend.Dockerfile       # multi-stage; also used for the Celery worker (different command)
│   ├── frontend.Dockerfile      # Node build stage -> nginx serve stage
│   └── docker-entrypoint.sh     # regenerates env-config.js from API_BASE_URL at container start
├── nginx/
│   ├── nginx.conf                # top-level nginx config
│   ├── default.conf              # HTTP server block: SPA + /api/ reverse proxy (tested)
│   └── default.ssl.conf.template # HTTPS server block template (needs a real domain — see DEPLOYMENT.md)
├── compose/
│   ├── docker-compose.dev.yml    # hot-reload backend, Vite dev server, all infra ports exposed
│   └── docker-compose.prod.yml   # hardened: no unnecessary public ports, resource limits, read-only FS
└── scripts/
    ├── init-minio.sh             # one-time bucket bootstrap
    ├── backup.sh                 # Postgres + Qdrant + MinIO backup
    └── restore.sh                # counterpart restore (destructive, confirms per-service)
```

Build contexts: `backend.Dockerfile`'s context is `backend/`; `frontend.Dockerfile`'s context is the **repository root** (it also needs `deployment/nginx/*.conf`). Both compose files set these paths correctly already — always invoke them from the repo root.
