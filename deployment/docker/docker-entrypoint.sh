#!/bin/sh
# Installed as a nginx:alpine /docker-entrypoint.d/ hook — nginx's own stock
# entrypoint runs every executable script here (in order) before starting
# nginx itself, so this just does its work and exits; no exec/CMD passthrough.
#
# Regenerates /usr/share/nginx/html/env-config.js from the API_BASE_URL
# container env var, so the SAME built image can point at a different backend
# in dev/staging/prod without a rebuild (see src/config.ts and
# frontend/public/env-config.js for how the frontend consumes this).
set -eu

: "${API_BASE_URL:=http://localhost:8000/api/v1}"

cat > /usr/share/nginx/html/env-config.js <<EOF
window.__ENV__ = {
  VITE_API_BASE_URL: "${API_BASE_URL}"
};
EOF
