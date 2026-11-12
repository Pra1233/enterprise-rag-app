// Resolves the API base URL at runtime first (window.__ENV__, injected by
// the Docker entrypoint from the API_BASE_URL container env var — see
// deployment/docker/frontend.Dockerfile), falling back to the build-time
// Vite value for local `npm run dev`. This is what lets one built frontend
// image be deployed against different backends without a rebuild.

declare global {
  interface Window {
    __ENV__?: {
      VITE_API_BASE_URL?: string
    }
  }
}

export function getApiBaseUrl(): string {
  return window.__ENV__?.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE_URL
}
