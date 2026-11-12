import type { AuthUser, UserRole } from './auth.types'

export interface AdminUser extends AuthUser {
  created_at: string
}

export interface CreateUserPayload {
  username: string
  password: string
  role: UserRole
  llm_request_limit: number
  upload_limit: number
}

export interface UpdateUserPayload {
  role?: UserRole
  llm_request_limit?: number
  upload_limit?: number
  is_active?: boolean
}

export interface AuditLogEntry {
  id: string
  username: string
  logged_in_at: string
  ip_address: string | null
  user_agent: string | null
  llm_requests_used: number
  llm_request_limit: number
  uploads_used: number
  upload_limit: number
}

export interface AuditLogResponse {
  items: AuditLogEntry[]
  total: number
  page: number
  page_size: number
}
