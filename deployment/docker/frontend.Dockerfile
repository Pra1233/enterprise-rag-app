# Multi-stage build: Vite production build, served by nginx (which also acts
# as the reverse proxy to the backend — see deployment/nginx/default.conf).
#
# Build context must be the REPOSITORY ROOT (not frontend/), since this also
# needs deployment/nginx/*.conf:
#   docker build -f deployment/docker/frontend.Dockerfile .

# --- Stage 1: build the static assets ---
FROM node:22-alpine AS builder

WORKDIR /build

# Installed from the lockfile (npm ci), not `npm install` — reproducible builds.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# VITE_API_BASE_URL baked in here is only the fallback used when window.__ENV__
# is absent (local `npm run dev`); the real, deployment-specific value is
# injected at container STARTUP by docker-entrypoint.sh (see src/config.ts) —
# one built image works across dev/staging/prod without rebuilding.
RUN npm run build

# --- Stage 2: serve with nginx ---
FROM nginx:1.27-alpine AS runtime

RUN rm -f /etc/nginx/conf.d/default.conf
COPY deployment/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deployment/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html
COPY deployment/docker/docker-entrypoint.sh /docker-entrypoint.d/40-env-config.sh

# nginx:alpine's own entrypoint already runs every executable script in
# /docker-entrypoint.d/ before starting nginx — reusing that hook means we
# don't need a custom ENTRYPOINT at all.
RUN chmod +x /docker-entrypoint.d/40-env-config.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --spider http://localhost/env-config.js || exit 1
