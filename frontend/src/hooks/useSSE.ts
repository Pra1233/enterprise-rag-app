import { useCallback, useRef, useState } from 'react'

import { getAuthToken } from '../api/authToken'
import type { ApiErrorBody } from '../types/api.types'
import type { SSEEvent } from '../types/chat.types'
import { SSEParser, toTypedSSEEvent } from '../utils/sseParser'

interface UseSSEOptions {
  onEvent: (event: SSEEvent) => void
  onError: (message: string) => void
  onComplete?: () => void
}

interface UseSSEResult {
  start: (url: string, body: unknown) => Promise<void>
  stop: () => void
  isStreaming: boolean
}

/**
 * Drives a streaming POST request by hand: fetch() + response.body.getReader()
 * + TextDecoder + AbortController. Deliberately NOT EventSource, which can't
 * send a POST body — the backend's /chat endpoint needs one.
 */
export function useSSE({ onEvent, onError, onComplete }: UseSSEOptions): UseSSEResult {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const start = useCallback(
    async (url: string, body: unknown) => {
      const controller = new AbortController()
      abortControllerRef.current = controller
      setIsStreaming(true)

      try {
        const token = getAuthToken()
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!response.ok || !response.body) {
          let message = `Request failed with status ${response.status}.`
          try {
            const errorBody: ApiErrorBody = await response.json()
            message = errorBody.error?.message ?? message
          } catch {
            // Response wasn't JSON (e.g. a proxy's plain-text 502) — keep the generic message.
          }
          onError(message)
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        const parser = new SSEParser()

        const dispatch = (raw: ReturnType<SSEParser['push']>) => {
          for (const frame of raw) {
            const typed = toTypedSSEEvent(frame)
            if (typed) onEvent(typed)
          }
        }

        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            dispatch(parser.flush())
            break
          }
          // stream: true keeps a trailing partial multi-byte UTF-8 sequence
          // buffered until the rest of it arrives, instead of corrupting it.
          const text = decoder.decode(value, { stream: true })
          dispatch(parser.push(text))
        }

        onComplete?.()
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          // User clicked Stop — not a failure, onComplete/onEvent already reflect what streamed.
        } else {
          onError(err instanceof Error ? err.message : 'A network error occurred while streaming the response.')
        }
      } finally {
        setIsStreaming(false)
        abortControllerRef.current = null
      }
    },
    [onEvent, onError, onComplete],
  )

  const stop = useCallback(() => {
    abortControllerRef.current?.abort()
  }, [])

  return { start, stop, isStreaming }
}
