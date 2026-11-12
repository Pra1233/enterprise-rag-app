import { Loader2 } from 'lucide-react'

interface LoaderProps {
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = { sm: 'size-4', md: 'size-6', lg: 'size-10' }

export function Loader({ label = 'Loading…', size = 'md' }: LoaderProps) {
  return (
    <div role="status" className="flex flex-col items-center justify-center gap-2 py-8 text-gray-500">
      <Loader2 className={`${sizeClasses[size]} animate-spin text-brand-500`} aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-gray-200 dark:bg-gray-700 ${className}`} />
}
