// Mirrors src/api/schemas/documents.py and src/api/schemas/ingestion.py (backend Phase 4).
// Note: the backend currently only accepts PDF uploads
// (allowed_upload_extensions = (".pdf",) in src/core/config.py) even though
// DocumentType itself also lists docx/txt/markdown/html for future use.

export type DocumentType = 'pdf' | 'docx' | 'txt' | 'markdown' | 'html'

export type DocumentStatus = 'queued' | 'parsing' | 'chunking' | 'embedding' | 'indexed' | 'failed'

export interface DocumentOut {
  document_id: string
  original_filename: string
  document_type: DocumentType
  author: string | null
  status: DocumentStatus
  error_message: string | null
  file_size_bytes: number
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  items: DocumentOut[]
  total: number
  page: number
  page_size: number
}

export interface UploadResponse {
  document_id: string
  task_id: string
  status: string
  message: string
}

export interface IngestionStatusResponse {
  task_id: string
  document_id: string
  status: DocumentStatus
  stage: DocumentStatus | null
  // Only ever populated if the worker itself reports it; the backend never
  // fabricates a percentage, so the UI must treat null as "unknown", not 0%.
  progress_percent: number | null
  error: string | null
}

export interface ReprocessResponse {
  document_id: string
  task_id: string
  status: string
  message: string
}

export interface DeleteResponse {
  document_id: string
  status: string
  message: string
}
