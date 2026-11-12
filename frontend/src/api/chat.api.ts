import type { ChatRequest, ChatResponse } from '../types/chat.types'
import { apiClient } from './axios'

// Only the non-streaming path goes through axios. Streaming uses fetch()
// directly in hooks/useSSE.ts, since axios can't expose a raw ReadableStream.
export const chatApi = {
  send: async (request: ChatRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post<ChatResponse>('/chat', request)
    return data
  },
}
