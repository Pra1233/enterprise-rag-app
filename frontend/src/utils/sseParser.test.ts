import { describe, expect, it } from 'vitest'

import { SSEParser, toTypedSSEEvent } from './sseParser'

describe('SSEParser', () => {
  it('parses a single complete event', () => {
    const parser = new SSEParser()
    const events = parser.push('event: token\ndata: {"token": "hi"}\n\n')
    expect(events).toEqual([{ event: 'token', data: '{"token": "hi"}' }])
  })

  it('parses multiple events delivered in one network chunk', () => {
    const parser = new SSEParser()
    const chunk =
      'event: token\ndata: {"token": "A"}\n\n' +
      'event: token\ndata: {"token": "B"}\n\n' +
      'event: done\ndata: {"status": "completed"}\n\n'

    const events = parser.push(chunk)

    expect(events).toHaveLength(3)
    expect(events[0]).toEqual({ event: 'token', data: '{"token": "A"}' })
    expect(events[1]).toEqual({ event: 'token', data: '{"token": "B"}' })
    expect(events[2]).toEqual({ event: 'done', data: '{"status": "completed"}' })
  })

  it('handles an event split across multiple network chunks', () => {
    const parser = new SSEParser()

    // The SSE frame is cut in the middle of the data line.
    expect(parser.push('event: token\ndata: {"tok')).toEqual([])
    expect(parser.push('en": "hello"}\n\n')).toEqual([{ event: 'token', data: '{"token": "hello"}' }])
  })

  it('handles a chunk boundary that splits the blank-line event terminator itself', () => {
    const parser = new SSEParser()
    expect(parser.push('event: done\ndata: {"status": "completed"}\n')).toEqual([])
    expect(parser.push('\n')).toEqual([{ event: 'done', data: '{"status": "completed"}' }])
  })

  it('joins multiline data fields with a newline, per the SSE spec', () => {
    const parser = new SSEParser()
    const events = parser.push('event: message\ndata: line one\ndata: line two\n\n')
    expect(events).toEqual([{ event: 'message', data: 'line one\nline two' }])
  })

  it('ignores comment/heartbeat lines', () => {
    const parser = new SSEParser()
    const events = parser.push(': heartbeat\n\nevent: done\ndata: {"status": "completed"}\n\n')
    expect(events).toEqual([{ event: 'done', data: '{"status": "completed"}' }])
  })

  it('flushes a final event that has no trailing blank line', () => {
    const parser = new SSEParser()
    expect(parser.push('event: token\ndata: {"token": "partial"}')).toEqual([])
    expect(parser.flush()).toEqual([{ event: 'token', data: '{"token": "partial"}' }])
  })

  it('flush returns nothing when the buffer is empty or whitespace', () => {
    const parser = new SSEParser()
    parser.push('event: done\ndata: {"status": "completed"}\n\n')
    expect(parser.flush()).toEqual([])
  })

  it('normalizes CRLF line endings', () => {
    const parser = new SSEParser()
    const events = parser.push('event: token\r\ndata: {"token": "crlf"}\r\n\r\n')
    expect(events).toEqual([{ event: 'token', data: '{"token": "crlf"}' }])
  })

  it('handles multi-byte UTF-8 content correctly once fully buffered', () => {
    const parser = new SSEParser()
    const events = parser.push('event: token\ndata: {"token": "café ✔"}\n\n')
    expect(JSON.parse(events[0].data)).toEqual({ token: 'café ✔' })
  })
})

describe('toTypedSSEEvent', () => {
  it('parses a token event', () => {
    const typed = toTypedSSEEvent({ event: 'token', data: '{"token": "hi"}' })
    expect(typed).toEqual({ event: 'token', data: { token: 'hi' } })
  })

  it('parses a citations event', () => {
    const typed = toTypedSSEEvent({
      event: 'citations',
      data: '{"sources": [{"document_id": "d1", "chunk_id": "c1", "source_uri": "u", "score": 0.9}]}',
    })
    expect(typed?.event).toBe('citations')
    expect(typed?.data).toEqual({
      sources: [{ document_id: 'd1', chunk_id: 'c1', source_uri: 'u', score: 0.9 }],
    })
  })

  it('parses an error event', () => {
    const typed = toTypedSSEEvent({ event: 'error', data: '{"code": "LLM_ERROR", "message": "boom"}' })
    expect(typed).toEqual({ event: 'error', data: { code: 'LLM_ERROR', message: 'boom' } })
  })

  it('returns null for invalid JSON instead of throwing', () => {
    expect(toTypedSSEEvent({ event: 'token', data: 'not json' })).toBeNull()
  })

  it('returns null for an unknown event name', () => {
    expect(toTypedSSEEvent({ event: 'mystery', data: '{}' })).toBeNull()
  })
})
