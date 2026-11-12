import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi } from './api/auth.api'
import { setAuthToken } from './api/authToken'
import { documentsApi } from './api/documents.api'
import App from './App'

vi.mock('./api/documents.api', () => ({
  documentsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  },
}))

vi.mock('./api/auth.api', () => ({
  authApi: {
    me: vi.fn().mockResolvedValue({
      id: 'user-1',
      username: 'test-user',
      role: 'user',
      llm_request_limit: 200,
      llm_requests_used: 0,
      upload_limit: 20,
      uploads_used: 0,
      is_active: true,
    }),
    login: vi.fn(),
  },
}))

beforeEach(() => {
  // AuthProvider calls GET /auth/me on mount if a token is present — seed one
  // so the app renders its authenticated shell instead of redirecting to /login.
  setAuthToken('test-token')
})

afterEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('App navigation', () => {
  it('renders the dashboard by default and navigates to the other sections', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Wait for AuthProvider's initial GET /auth/me to resolve.
    await vi.waitFor(() => expect(authApi.me).toHaveBeenCalled())

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: /ai chat/i }))
    expect(await screen.findByRole('heading', { name: 'AI Chat' })).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: /documents/i }))
    expect(await screen.findByRole('heading', { name: 'Documents' })).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: /settings/i }))
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()

    expect(documentsApi.list).toHaveBeenCalled()
  })
})
