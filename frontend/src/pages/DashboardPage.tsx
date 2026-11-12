import { CheckCircle2, FileText, Loader2, MessageSquare, UploadCloud, XCircle } from 'lucide-react'
import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'

import { DocumentStatusBadge } from '../components/documents/DocumentStatus'
import { EmptyState } from '../components/common/EmptyState'
import { Skeleton } from '../components/common/Loader'
import { useDocumentsList } from '../hooks/useDocuments'
import { formatDate, formatFileSize } from '../utils/formatters'

// There is no dedicated dashboard-stats endpoint on the backend (identified
// gap — see src/api/routes/documents.py), so these counts are derived from
// the real GET /documents list endpoint via its `total` field, filtered by
// status. This costs a few extra requests but every number here is real,
// never hardcoded.
export default function DashboardPage() {
  const totalQuery = useDocumentsList({ page: 1, page_size: 1 })
  const indexedQuery = useDocumentsList({ page: 1, page_size: 1, status: 'indexed' })
  const failedQuery = useDocumentsList({ page: 1, page_size: 1, status: 'failed' })
  const recentQuery = useDocumentsList({ page: 1, page_size: 5 })

  const isLoadingStats = totalQuery.isLoading || indexedQuery.isLoading || failedQuery.isLoading
  const total = totalQuery.data?.total ?? 0
  const indexed = indexedQuery.data?.total ?? 0
  const failed = failedQuery.data?.total ?? 0
  const processing = Math.max(0, total - indexed - failed)

  const stats: { label: string; value: number; icon: ComponentType<{ className?: string }>; color: string }[] = [
    { label: 'Total documents', value: total, icon: FileText, color: 'text-gray-500' },
    { label: 'Successfully processed', value: indexed, icon: CheckCircle2, color: 'text-green-600' },
    { label: 'Currently processing', value: processing, icon: Loader2, color: 'text-blue-600' },
    { label: 'Failed', value: failed, icon: XCircle, color: 'text-red-600' },
  ]

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 p-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</span>
              <Icon className={`size-4 ${color}`} />
            </div>
            {isLoadingStats ? (
              <Skeleton className="mt-2 h-7 w-12" />
            ) : (
              <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">{value}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <Link
          to="/documents"
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          <UploadCloud className="size-4" /> Upload a document
        </Link>
        <Link
          to="/chat"
          className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          <MessageSquare className="size-4" /> Start a conversation
        </Link>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">Recent uploads</h2>
        {recentQuery.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : !recentQuery.data || recentQuery.data.items.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No documents uploaded yet"
            description="Upload your first PDF to get started."
          />
        ) : (
          <div className="flex flex-col gap-2">
            {recentQuery.data.items.map((doc) => (
              <div
                key={doc.document_id}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-gray-800 dark:text-gray-100">{doc.original_filename}</p>
                  <p className="text-xs text-gray-400">
                    {formatDate(doc.created_at)} · {formatFileSize(doc.file_size_bytes)}
                  </p>
                </div>
                <DocumentStatusBadge status={doc.status} />
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
