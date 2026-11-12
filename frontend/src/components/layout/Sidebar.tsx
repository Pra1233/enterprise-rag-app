import { ChevronLeft, ChevronRight, FileText, LayoutDashboard, LogOut, MessageSquare, Settings, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink } from 'react-router-dom'

import { useAuth } from '../../context/AuthContext'

interface SidebarProps {
  mobileOpen: boolean
  onCloseMobile: () => void
}

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/chat', label: 'AI Chat', icon: MessageSquare, end: false },
  { to: '/documents', label: 'Documents', icon: FileText, end: false },
  { to: '/settings', label: 'Settings', icon: Settings, end: false },
]

function SidebarContent({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { user, logout } = useAuth()
  const items =
    user?.role === 'admin' ? [...navItems, { to: '/admin', label: 'Admin Panel', icon: ShieldCheck, end: false }] : navItems

  return (
    <>
      <nav className="flex flex-1 flex-col gap-1 px-2 py-4">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
              }`
            }
          >
            <Icon className="size-5 shrink-0" aria-hidden="true" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-gray-200 px-4 py-4 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
            {user?.username.slice(0, 1).toUpperCase() ?? 'U'}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                {user?.username ?? 'Signed out'}
              </p>
              <p className="truncate text-xs text-gray-400 capitalize">{user?.role}</p>
            </div>
          )}
          {!collapsed && (
            <button
              type="button"
              onClick={logout}
              aria-label="Log out"
              className="shrink-0 rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
            >
              <LogOut className="size-4" />
            </button>
          )}
        </div>
      </div>
    </>
  )
}

export function Sidebar({ mobileOpen, onCloseMobile }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <>
      <aside
        className={`hidden shrink-0 flex-col border-r border-gray-200 bg-white transition-[width] duration-200 lg:flex dark:border-gray-700 dark:bg-gray-900 ${
          collapsed ? 'w-16' : 'w-60'
        }`}
      >
        <div className="flex items-center justify-between px-3 py-4">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
              R
            </div>
            {!collapsed && (
              <span className="truncate text-base font-semibold text-gray-900 dark:text-gray-100">
                RAG Console
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
          </button>
        </div>
        <SidebarContent collapsed={collapsed} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={onCloseMobile} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-white dark:bg-gray-900">
            <div className="flex items-center justify-between px-4 py-4">
              <span className="text-base font-semibold text-gray-900 dark:text-gray-100">RAG Console</span>
              <button
                type="button"
                onClick={onCloseMobile}
                aria-label="Close menu"
                className="rounded-md p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="size-5" />
              </button>
            </div>
            <SidebarContent collapsed={false} onNavigate={onCloseMobile} />
          </aside>
        </div>
      )}
    </>
  )
}
