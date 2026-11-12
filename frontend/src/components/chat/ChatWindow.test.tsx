import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createSSEStream, renderWithProviders } from '../../test/utils'
import { ChatWindow } from './ChatWindow'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('ChatWindow', () => {
  it('sends a message and renders the streamed assistant reply with citations', async () => {
    const chunks = [
      'event: token\ndata: {"token": "Project Aurora"}\n\n',
      'event: token\ndata: {"token": " is led by Dr. Vasquez."}\n\n',
      'event: citations\ndata: {"sources": [{"document_id": "d1", "chunk_id": "c1c1c1c1-0000-0000-0000-000000000000", "source_uri": "tenant-1/d1/report.pdf", "score": 0.95}]}\n\n',
      'event: done\ndata: {"status": "completed"}\n\n',
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        const body = JSON.parse(init?.body as string)
        expect(body).toMatchObject({ query: 'Who leads Project Aurora?', stream: true })
        return { ok: true, body: createSSEStream(chunks) }
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<ChatWindow conversationId="conv-1" />)

    const textbox = screen.getByPlaceholderText(/ask a question/i)
    await user.type(textbox, 'Who leads Project Aurora?')
    await user.keyboard('{Enter}')

    expect(screen.getByText('Who leads Project Aurora?')).toBeInTheDocument()

    await waitFor(() =>
      expect(screen.getByText(/Project Aurora is led by Dr\. Vasquez\./)).toBeInTheDocument(),
    )

    // Citations are rendered but collapsed by default.
    const citationsToggle = await screen.findByRole('button', { name: /1 source/i })
    await user.click(citationsToggle)
    expect(await screen.findByText(/report\.pdf/)).toBeInTheDocument()
  })

  it('adds a newline on Shift+Enter instead of sending', async () => {
    vi.stubGlobal('fetch', vi.fn())
    const user = userEvent.setup()
    renderWithProviders(<ChatWindow conversationId="conv-1" />)

    const textbox = screen.getByPlaceholderText<HTMLTextAreaElement>(/ask a question/i)
    await user.type(textbox, 'line one')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    await user.type(textbox, 'line two')

    expect(textbox.value).toBe('line one\nline two')
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('stops generation when the Stop button is clicked', async () => {
    let abortedSignal: AbortSignal | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => {
        abortedSignal = init?.signal ?? undefined
        return new Promise((_resolve, reject) => {
          abortedSignal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<ChatWindow conversationId="conv-1" />)

    await user.type(screen.getByPlaceholderText(/ask a question/i), 'Hello')
    await user.keyboard('{Enter}')

    const stopButton = await screen.findByRole('button', { name: /stop generating/i })
    await user.click(stopButton)

    expect(abortedSignal?.aborted).toBe(true)
    expect(await screen.findByRole('button', { name: /send message/i })).toBeInTheDocument()
  })

  it('renders a user-facing error message when the stream reports an error event', async () => {
    const chunks = ['event: error\ndata: {"code": "LLM_ERROR", "message": "Unable to generate response"}\n\n']
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, body: createSSEStream(chunks) })),
    )

    const user = userEvent.setup()
    renderWithProviders(<ChatWindow conversationId="conv-1" />)

    await user.type(screen.getByPlaceholderText(/ask a question/i), 'Hello')
    await user.keyboard('{Enter}')

    expect(await screen.findByText('Unable to generate response')).toBeInTheDocument()
  })
})
