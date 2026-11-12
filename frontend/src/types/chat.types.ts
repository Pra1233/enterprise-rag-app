// Mirrors src/api/schemas/chat.py and the SSE protocol emitted by
// src/api/routes/chat.py (backend Phase 4).

export interface ChatFilters {
  document_type?: string
}

export interface ChatRequest {
  query: string
  conversation_id?: string
  filters?: ChatFilters
  stream: boolean
}

export interface ChatCitation {
  document_id: string
  chunk_id: string
  source_uri: string
  score: number
}

export interface ChatResponse {
  answer: string
  citations: ChatCitation[]
  conversation_id: string | null
  cached: boolean
}

// --- SSE event payloads ---

export interface SSETokenEvent {
  token: string
}

export interface SSECitationsEvent {
  sources: ChatCitation[]
}

export interface SSEDoneEvent {
  status: string
}

export interface SSEErrorEvent {
  code: string
  message: string
}

export type SSEEvent =
  | { event: 'token'; data: SSETokenEvent }
  | { event: 'citations'; data: SSECitationsEvent }
  | { event: 'done'; data: SSEDoneEvent }
  | { event: 'error'; data: SSEErrorEvent }

// --- Frontend-only UI state (not part of the backend contract) ---

export type MessageStatus = 'pending' | 'streaming' | 'done' | 'error'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: ChatCitation[]
  status: MessageStatus
  errorMessage?: string
  createdAt: number
}

export interface Conversation {
  id: string
  title: string
  createdAt: number
}
