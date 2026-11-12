import { FileText, X } from 'lucide-react'

import type { UploadItem } from '../../hooks/useDocumentUpload'
import { DocumentStatusBadge } from './DocumentStatus'

interface UploadProgressProps {
  items: UploadItem[]
  onDismiss: (id: string) => void
}

export function UploadProgress({ items, onDismiss }: UploadProgressProps) {
  if (items.length === 0) return null

  return (
    <div className="flex flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800"
        >
          <FileText className="size-5 shrink-0 text-gray-400" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-gray-800 dark:text-gray-100">{item.fileName}</p>

            {item.status === 'uploading' ? (
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className="h-full rounded-full bg-brand-500 transition-all"
                  style={{ width: `${item.uploadProgress}%` }}
                />
              </div>
            ) : item.status === 'upload_failed' ? (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">{item.error ?? 'Upload failed.'}</p>
            ) : (
              <div className="mt-1 flex items-center gap-2">
                <DocumentStatusBadge status={item.status} />
                {item.error && <span className="text-xs text-red-600 dark:text-red-400">{item.error}</span>}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(item.id)}
            aria-label={`Dismiss ${item.fileName}`}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
