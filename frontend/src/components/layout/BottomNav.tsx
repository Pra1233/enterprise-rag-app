import { FileText, LayoutDashboard, Menu, MessageSquare } from 'lucide-react'
import { NavLink } from 'react-router-dom'

interface BottomNavProps {
  onOpenMore: () => void
}

const items = [
  { to: '/', label: 'Home', icon: LayoutDashboard, end: true },
  { to: '/chat', label: 'Chat', icon: MessageSquare, end: false },
  { to: '/documents', label: 'Docs', icon: FileText, end: false },
]

export function BottomNav({ onOpenMore }: BottomNavProps) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-stretch border-t border-gray-200 bg-white/95 backdrop-blur lg:hidden dark:border-gray-700 dark:bg-gray-900/95">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center justify-center gap-0.5 text-xs font-medium transition-colors ${
              isActive ? 'text-brand-600 dark:text-brand-400' : 'text-gray-500 dark:text-gray-400'
            }`
          }
        >
          <Icon className="size-5" aria-hidden="true" />
          {label}
        </NavLink>
      ))}
      <button
        type="button"
        onClick={onOpenMore}
        className="flex flex-1 flex-col items-center justify-center gap-0.5 text-xs font-medium text-gray-500 dark:text-gray-400"
      >
        <Menu className="size-5" aria-hidden="true" />
        More
      </button>
    </nav>
  )
}
