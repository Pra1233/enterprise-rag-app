import { CheckCircle2, Loader2, XCircle } from 'lucide-react'

import type { DocumentStatus as Status } from '../../types/document.types'

const STATUS_STYLES: Record<Status, string> = {
  queued: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
  parsing: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  chunking: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  embedding: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  indexed: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
  failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
}

const STATUS_LABELS: Record<Status, string> = {
  queued: 'Queued',
  parsing: 'Parsing',
  chunking: 'Chunking',
  embedding: 'Embedding',
  indexed: 'Indexed',
  failed: 'Failed',
}

const IN_PROGRESS = new Set<Status>(['queued', 'parsing', 'chunking', 'embedding'])

export function DocumentStatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {IN_PROGRESS.has(status) && <Loader2 className="size-3 animate-spin" />}
      {status === 'indexed' && <CheckCircle2 className="size-3" />}
      {status === 'failed' && <XCircle className="size-3" />}
      {STATUS_LABELS[status]}
    </span>
  )
}
