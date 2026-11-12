import type { ReactNode } from 'react'

export function MainContent({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <main className={`flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-950 ${className}`}>{children}</main>
}
