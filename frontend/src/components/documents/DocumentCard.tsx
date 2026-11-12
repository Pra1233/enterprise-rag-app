import { Eye, FileText, RefreshCw, Trash2 } from 'lucide-react'

import type { DocumentOut } from '../../types/document.types'
import { formatDate, formatFileSize } from '../../utils/formatters'
import { DocumentStatusBadge } from './DocumentStatus'

interface DocumentCardProps {
  document: DocumentOut
  onView: (doc: DocumentOut) => void
  onDelete: (doc: DocumentOut) => void
  onReprocess: (doc: DocumentOut) => void
  isDeleting?: boolean
  isReprocessing?: boolean
}

export function DocumentCard({
  document,
  onView,
  onDelete,
  onReprocess,
  isDeleting,
  isReprocessing,
}: DocumentCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 sm:flex-row sm:items-center dark:border-gray-700 dark:bg-gray-800">
      <FileText className="hidden size-8 shrink-0 text-gray-400 sm:block" aria-hidden="true" />

      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-gray-900 dark:text-gray-100">{document.original_filename}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
          <span className="uppercase">{document.document_type}</span>
          <span>{formatFileSize(document.file_size_bytes)}</span>
          <span>Uploaded {formatDate(document.created_at)}</span>
          {document.author && <span>by {document.author}</span>}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <DocumentStatusBadge status={document.status} />

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onView(document)}
            aria-label={`View details for ${document.original_filename}`}
            title="View details"
            className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700"
          >
            <Eye className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => onReprocess(document)}
            disabled={isReprocessing}
            aria-label={`Reprocess ${document.original_filename}`}
            title="Reprocess"
            className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50 dark:hover:bg-gray-700"
          >
            <RefreshCw className={`size-4 ${isReprocessing ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={() => onDelete(document)}
            disabled={isDeleting}
            aria-label={`Delete ${document.original_filename}`}
            title="Delete"
            className="rounded-md p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-950"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
