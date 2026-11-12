import type {
  SSECitationsEvent,
  SSEDoneEvent,
  SSEErrorEvent,
  SSEEvent,
  SSETokenEvent,
} from '../types/chat.types'

/** One raw, un-typed SSE frame: an event name plus its (possibly multiline) data. */
export interface RawSSEEvent {
  event: string
  data: string
}

/**
 * Incremental SSE parser. Feed it decoded text chunks as they arrive from a
 * fetch() ReadableStream; it buffers across chunk boundaries so it never
 * assumes one network chunk equals one SSE event (chunks can split an event
 * in half, or contain several events back to back).
 */
export class SSEParser {
  private buffer = ''

  /** Push a newly-decoded text chunk; returns any complete events found so far. */
  push(chunk: string): RawSSEEvent[] {
    this.buffer += chunk.replace(/\r\n/g, '\n')

    const events: RawSSEEvent[] = []
    let boundary: number
    while ((boundary = this.buffer.indexOf('\n\n')) !== -1) {
      const rawBlock = this.buffer.slice(0, boundary)
      this.buffer = this.buffer.slice(boundary + 2)
      const event = parseBlock(rawBlock)
      if (event) events.push(event)
    }
    return events
  }

  /** Call once the stream has ended, to flush a final event with no trailing blank line. */
  flush(): RawSSEEvent[] {
    const remaining = this.buffer
    this.buffer = ''
    if (!remaining.trim()) return []
    const event = parseBlock(remaining)
    return event ? [event] : []
  }
}

function parseBlock(rawBlock: string): RawSSEEvent | null {
  let eventName = 'message'
  const dataLines: string[] = []

  for (const line of rawBlock.split('\n')) {
    if (line === '' || line.startsWith(':')) continue // blank line within block / comment / heartbeat
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      // Per the SSE spec, a single leading space after the colon is stripped, not all whitespace.
      dataLines.push(line.slice('data:'.length).replace(/^ /, ''))
    }
  }

  if (dataLines.length === 0) return null
  return { event: eventName, data: dataLines.join('\n') }
}

/** Parse a raw SSE frame's JSON data payload into one of the backend's typed events. */
export function toTypedSSEEvent(raw: RawSSEEvent): SSEEvent | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw.data)
  } catch {
    return null
  }

  switch (raw.event) {
    case 'token':
      return { event: 'token', data: parsed as SSETokenEvent }
    case 'citations':
      return { event: 'citations', data: parsed as SSECitationsEvent }
    case 'done':
      return { event: 'done', data: parsed as SSEDoneEvent }
    case 'error':
      return { event: 'error', data: parsed as SSEErrorEvent }
    default:
      return null
  }
}
