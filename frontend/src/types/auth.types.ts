export type UserRole = 'admin' | 'user'

export interface AuthUser {
  id: string
  username: string
  role: UserRole
  llm_request_limit: number
  llm_requests_used: number
  upload_limit: number
  uploads_used: number
  is_active: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}
