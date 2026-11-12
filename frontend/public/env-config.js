// Runtime configuration, overwritten at container startup by
// deployment/docker/frontend.Dockerfile's entrypoint (envsubst over this
// file) from the API_BASE_URL environment variable. This file lets one built
// image be deployed to multiple environments without a rebuild — Vite's
// import.meta.env.* values are otherwise baked in at build time.
//
// Loaded before the main bundle (see index.html). In local `npm run dev`,
// this default is used, and src/config.ts falls back to import.meta.env if
// window.__ENV__ is absent entirely.
window.__ENV__ = {
  VITE_API_BASE_URL: "http://localhost:8000/api/v1",
};
