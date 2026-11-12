import { useCallback, useEffect, useRef, useState } from 'react'

import { getApiBaseUrl } from '../config'
import type { ChatMessage, SSEEvent } from '../types/chat.types'
import { useSSE } from './useSSE'

const API_BASE = getApiBaseUrl()

function createId(): string {
  return crypto.randomUUID()
}

function storageKey(conversationId: string): string {
  return `rag_chat_history_${conversationId}`
}

function loadStoredMessages(conversationId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(storageKey(conversationId))
    return raw ? (JSON.parse(raw) as ChatMessage[]) : []
  } catch {
    return []
  }
}

// The backend accepts conversation_id in ChatRequest but does not persist or
// return message history for it — there is no GET /conversations endpoint.
// Message transcripts are therefore cached client-side only, per browser.
export function useChat(conversationId: string, documentTypeFilter?: string, onFirstMessage?: (query: string) => void) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadStoredMessages(conversationId))
  const activeAssistantIdRef = useRef<string | null>(null)

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(conversationId), JSON.stringify(messages))
    } catch {
      // Storage can be full/unavailable (private browsing) — the conversation
      // still works in-memory for this session, it just won't persist.
    }
  }, [conversationId, messages])

  const patchAssistant = useCallback((patch: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) => {
    const id = activeAssistantIdRef.current
    if (!id) return
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...(typeof patch === 'function' ? patch(m) : patch) } : m)),
    )
  }, [])

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.event) {
        case 'token':
          patchAssistant((m) => ({ content: m.content + event.data.token, status: 'streaming' }))
          break
        case 'citations':
          patchAssistant({ citations: event.data.sources })
          break
        case 'done':
          patchAssistant({ status: 'done' })
          break
        case 'error':
          patchAssistant({ status: 'error', errorMessage: event.data.message })
          break
      }
    },
    [patchAssistant],
  )

  const handleError = useCallback(
    (message: string) => {
      patchAssistant({ status: 'error', errorMessage: message || 'Something went wrong.' })
    },
    [patchAssistant],
  )

  const { start, stop, isStreaming } = useSSE({ onEvent: handleEvent, onError: handleError })

  const sendMessage = useCallback(
    (query: string) => {
      const trimmed = query.trim()
      if (!trimmed) return

      if (messages.length === 0) {
        onFirstMessage?.(trimmed)
      }

      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: trimmed,
        status: 'done',
        createdAt: Date.now(),
      }
      const assistantMessage: ChatMessage = {
        id: createId(),
        role: 'assistant',
        content: '',
        status: 'pending',
        createdAt: Date.now(),
      }
      activeAssistantIdRef.current = assistantMessage.id
      setMessages((prev) => [...prev, userMessage, assistantMessage])

      void start(`${API_BASE}/chat`, {
        query: trimmed,
        conversation_id: conversationId,
        filters: documentTypeFilter ? { document_type: documentTypeFilter } : undefined,
        stream: true,
      })
    },
    [start, conversationId, documentTypeFilter, messages.length, onFirstMessage],
  )

  const stopGeneration = useCallback(() => {
    stop()
    patchAssistant((m) => (m.status === 'streaming' || m.status === 'pending' ? { status: 'done' } : {}))
  }, [stop, patchAssistant])

  const clearConversation = useCallback(() => {
    setMessages([])
    activeAssistantIdRef.current = null
    try {
      localStorage.removeItem(storageKey(conversationId))
    } catch {
      // ignore
    }
  }, [conversationId])

  return { messages, sendMessage, stopGeneration, clearConversation, isStreaming }
}
