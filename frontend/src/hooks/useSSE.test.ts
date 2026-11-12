import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createSSEStream } from '../test/utils'
import type { SSEEvent } from '../types/chat.types'
import { useSSE } from './useSSE'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useSSE', () => {
  it('streams token/citations/done events in order from a mocked fetch response', async () => {
    const chunks = [
      'event: token\ndata: {"token": "Hello"}\n\n',
      'event: token\ndata: {"token": " world"}\n\n',
      'event: citations\ndata: {"sources": [{"document_id": "d1", "chunk_id": "c1", "source_uri": "u", "score": 0.9}]}\n\n',
      'event: done\ndata: {"status": "completed"}\n\n',
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, body: createSSEStream(chunks) })),
    )

    const received: SSEEvent[] = []
    const onComplete = vi.fn()
    const { result } = renderHook(() => useSSE({ onEvent: (e) => received.push(e), onError: vi.fn(), onComplete }))

    await act(async () => {
      await result.current.start('http://api.test/chat', { query: 'hi', stream: true })
    })

    expect(received.map((e) => e.event)).toEqual(['token', 'token', 'citations', 'done'])
    expect(received[0]).toEqual({ event: 'token', data: { token: 'Hello' } })
    expect(onComplete).toHaveBeenCalledOnce()
    expect(result.current.isStreaming).toBe(false)
  })

  it('aborts the request when stop() is called and does not report it as an error', async () => {
    const onError = vi.fn()
    let capturedSignal: AbortSignal | undefined

    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => {
        capturedSignal = init?.signal ?? undefined
        return new Promise((_resolve, reject) => {
          capturedSignal?.addEventListener('abort', () => {
            const err = new DOMException('Aborted', 'AbortError')
            reject(err)
          })
        })
      }),
    )

    const { result } = renderHook(() => useSSE({ onEvent: vi.fn(), onError }))

    let startPromise: Promise<void>
    act(() => {
      startPromise = result.current.start('http://api.test/chat', { query: 'hi', stream: true })
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    act(() => {
      result.current.stop()
    })

    await act(async () => {
      await startPromise
    })

    expect(onError).not.toHaveBeenCalled()
    expect(result.current.isStreaming).toBe(false)
  })

  it('surfaces a server error response via onError without throwing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 503,
        body: null,
        json: async () => ({ error: { code: 'VECTOR_STORE_UNAVAILABLE', message: 'Search index is down' } }),
      })),
    )

    const onError = vi.fn()
    const { result } = renderHook(() => useSSE({ onEvent: vi.fn(), onError }))

    await act(async () => {
      await result.current.start('http://api.test/chat', { query: 'hi', stream: true })
    })

    expect(onError).toHaveBeenCalledWith('Search index is down')
  })

  it('surfaces a network failure via onError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    const onError = vi.fn()
    const { result } = renderHook(() => useSSE({ onEvent: vi.fn(), onError }))

    await act(async () => {
      await result.current.start('http://api.test/chat', { query: 'hi', stream: true })
    })

    expect(onError).toHaveBeenCalledWith('Failed to fetch')
  })
})
