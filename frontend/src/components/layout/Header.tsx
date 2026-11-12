import { FileText, Menu, Moon, Sun, User } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../context/AuthContext'
import { useDocumentsList } from '../../hooks/useDocuments'
import { useTheme } from '../../hooks/useTheme'

interface HeaderProps {
  title: string
  onOpenMobileNav: () => void
}

export function Header({ title, onOpenMobileNav }: HeaderProps) {
  const { theme, toggleTheme } = useTheme()
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  // Real document-context indicator (count of indexed docs), not a fabricated
  // search feature — the backend has no document search endpoint.
  const { data } = useDocumentsList({ page: 1, page_size: 1, status: 'indexed' })

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenMobileNav}
          aria-label="Open menu"
          className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 lg:hidden dark:hover:bg-gray-800"
        >
          <Menu className="size-5" />
        </button>
        <h1 className="text-base font-semibold text-gray-900 dark:text-gray-100">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        <div
          className="hidden items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600 sm:flex dark:bg-gray-800 dark:text-gray-300"
          title="Number of fully-indexed documents available to chat against"
        >
          <FileText className="size-3.5" />
          <span>{data ? `${data.total} indexed` : '—'}</span>
        </div>

        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          {theme === 'dark' ? <Sun className="size-4.5" /> : <Moon className="size-4.5" />}
        </button>

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex size-8 items-center justify-center rounded-full bg-gray-200 text-gray-600 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-300"
          >
            <User className="size-4" />
          </button>
          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-10 w-56 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-800"
            >
              <div className="border-b border-gray-100 px-3 py-2 text-xs text-gray-400 dark:border-gray-700">
                Signed in as <span className="font-medium text-gray-600 dark:text-gray-300">{user?.username}</span>{' '}
                <span className="capitalize">({user?.role})</span>
              </div>
              <Link
                to="/settings"
                role="menuitem"
                onClick={() => setMenuOpen(false)}
                className="block px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-700"
              >
                Settings
              </Link>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  logout()
                  setMenuOpen(false)
                }}
                className="block w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
