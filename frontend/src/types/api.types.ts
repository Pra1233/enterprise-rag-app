// Mirrors the error envelope produced by
// src/api/middleware/error_handler.py (backend Phase 4):
//   { "error": { "code": "...", "message": "...", "request_id": "..." } }

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    request_id: string
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string

  constructor(status: number, code: string, message: string, requestId: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}
