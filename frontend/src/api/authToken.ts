// The Phase 4 backend requires a Bearer JWT on every endpoint but exposes no
// login/token-issuing endpoint of its own (dev-only HS256 auth — see
// src/api/dependencies.py). Until a real IdP exists, the token is pasted in
// on the Settings page and kept in localStorage.

const TOKEN_KEY = 'rag_auth_token'

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}
