import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ingestionApi } from '../../api/ingestion.api'
import { renderWithProviders } from '../../test/utils'
import { DocumentUpload } from './DocumentUpload'

vi.mock('../../api/ingestion.api', () => ({
  ingestionApi: {
    upload: vi.fn(),
    getStatus: vi.fn(),
  },
}))

afterEach(() => {
  vi.clearAllMocks()
})

function makeFile(name: string, sizeBytes: number, type = 'application/pdf'): File {
  const file = new File([new Uint8Array(sizeBytes)], name, { type })
  return file
}

describe('DocumentUpload', () => {
  it('uploads a valid PDF and shows upload progress, then the queued status', async () => {
    vi.mocked(ingestionApi.upload).mockImplementation(async (_file, _author, onProgress) => {
      onProgress?.(50)
      onProgress?.(100)
      return { document_id: 'doc-1', task_id: 'task-1', status: 'queued', message: 'Document ingestion started' }
    })
    vi.mocked(ingestionApi.getStatus).mockResolvedValue({
      task_id: 'task-1',
      document_id: 'doc-1',
      status: 'queued',
      stage: 'queued',
      progress_percent: null,
      error: null,
    })

    renderWithProviders(<DocumentUpload />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeFile('report.pdf', 1024)
    await userEvent.upload(input, file)

    await waitFor(() => expect(ingestionApi.upload).toHaveBeenCalledWith(file, undefined, expect.any(Function)))
    expect(await screen.findByText('report.pdf')).toBeInTheDocument()
    expect(await screen.findByText('Queued')).toBeInTheDocument()
  })

  it('rejects a non-PDF file dropped onto the dropzone (bypasses the input accept filter)', async () => {
    renderWithProviders(<DocumentUpload />)

    const file = makeFile('notes.txt', 100, 'text/plain')
    const dropzone = screen.getByText(/drag and drop a pdf here/i).closest('div') as HTMLElement

    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } })

    expect(await screen.findByRole('alert')).toHaveTextContent(/not a PDF/i)
    expect(ingestionApi.upload).not.toHaveBeenCalled()
  })

  it('rejects a file that exceeds the size limit', async () => {
    renderWithProviders(<DocumentUpload />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const oversized = makeFile('huge.pdf', 51 * 1024 * 1024)
    await userEvent.upload(input, oversized)

    expect(await screen.findByRole('alert')).toHaveTextContent(/exceeds/i)
    expect(ingestionApi.upload).not.toHaveBeenCalled()
  })

  it('shows an error message when the upload request itself fails', async () => {
    vi.mocked(ingestionApi.upload).mockRejectedValue(new Error('Network error'))

    renderWithProviders(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, makeFile('report.pdf', 1024))

    expect(await screen.findByText('Network error')).toBeInTheDocument()
  })
})
