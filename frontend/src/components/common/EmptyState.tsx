import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-gray-300 px-6 py-16 text-center dark:border-gray-700">
      <Icon className="size-10 text-gray-300 dark:text-gray-600" aria-hidden="true" />
      <h3 className="text-base font-medium text-gray-900 dark:text-gray-100">{title}</h3>
      {description && <p className="max-w-sm text-sm text-gray-500 dark:text-gray-400">{description}</p>}
      {action}
    </div>
  )
}
