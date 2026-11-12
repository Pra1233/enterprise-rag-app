import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { documentsApi } from '../../api/documents.api'
import { ApiError } from '../../types/api.types'
import { renderWithProviders } from '../../test/utils'
import type { DocumentOut } from '../../types/document.types'
import { DocumentList } from './DocumentList'

vi.mock('../../api/documents.api', () => ({
  documentsApi: {
    list: vi.fn(),
    remove: vi.fn(),
    reprocess: vi.fn(),
  },
}))

const sampleDoc: DocumentOut = {
  document_id: 'doc-1',
  original_filename: 'report.pdf',
  document_type: 'pdf',
  author: 'Jane Doe',
  status: 'indexed',
  error_message: null,
  file_size_bytes: 204_800,
  created_at: '2026-01-01T12:00:00Z',
  updated_at: '2026-01-01T12:05:00Z',
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('DocumentList', () => {
  it('renders documents returned by the API (React Query loading -> success)', async () => {
    vi.mocked(documentsApi.list).mockResolvedValue({ items: [sampleDoc], total: 1, page: 1, page_size: 10 })

    renderWithProviders(<DocumentList />)

    expect(await screen.findByText('report.pdf')).toBeInTheDocument()
    expect(screen.getByText('Indexed', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('1 document')).toBeInTheDocument()
  })

  it('shows an empty state when there are no documents', async () => {
    vi.mocked(documentsApi.list).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 })

    renderWithProviders(<DocumentList />)

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument()
  })

  it('shows an error state when the list request fails (React Query error state)', async () => {
    vi.mocked(documentsApi.list).mockRejectedValue(new ApiError(503, 'VECTOR_STORE_UNAVAILABLE', 'down', 'req-1'))

    renderWithProviders(<DocumentList />)

    expect(await screen.findByRole('alert')).toHaveTextContent(/search index is temporarily unavailable/i)
  })

  it('deletes a document after confirmation and refreshes the list', async () => {
    vi.mocked(documentsApi.list).mockResolvedValue({ items: [sampleDoc], total: 1, page: 1, page_size: 10 })
    vi.mocked(documentsApi.remove).mockResolvedValue({ document_id: 'doc-1', status: 'deleted', message: 'ok' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    const user = userEvent.setup()
    renderWithProviders(<DocumentList />)

    const row = (await screen.findByText('report.pdf')).closest('div.rounded-lg') as HTMLElement
    await user.click(within(row).getByRole('button', { name: /delete/i }))

    await waitFor(() => expect(documentsApi.remove).toHaveBeenCalledWith('doc-1'))
    // The list is refetched after a successful delete (query invalidation).
    await waitFor(() => expect(documentsApi.list).toHaveBeenCalledTimes(2))
  })

  it('does not delete when the user cancels the confirmation dialog', async () => {
    vi.mocked(documentsApi.list).mockResolvedValue({ items: [sampleDoc], total: 1, page: 1, page_size: 10 })
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    const user = userEvent.setup()
    renderWithProviders(<DocumentList />)

    const row = (await screen.findByText('report.pdf')).closest('div.rounded-lg') as HTMLElement
    await user.click(within(row).getByRole('button', { name: /delete/i }))

    expect(documentsApi.remove).not.toHaveBeenCalled()
  })
})
