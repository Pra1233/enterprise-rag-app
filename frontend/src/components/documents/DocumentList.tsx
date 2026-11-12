import { ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { useState } from 'react'

import { useToast } from '../common/ToastProvider'
import { EmptyState } from '../common/EmptyState'
import { ErrorMessage, toUserMessage } from '../common/ErrorMessage'
import { Skeleton } from '../common/Loader'
import { Modal } from '../common/Modal'
import { useDeleteDocument, useDocumentsList, useReprocessDocument } from '../../hooks/useDocuments'
import type { DocumentOut, DocumentStatus } from '../../types/document.types'
import { formatDate, formatFileSize } from '../../utils/formatters'
import { DocumentCard } from './DocumentCard'

const PAGE_SIZE = 10

const STATUS_FILTERS: { label: string; value: DocumentStatus | '' }[] = [
  { label: 'All statuses', value: '' },
  { label: 'Queued', value: 'queued' },
  { label: 'Processing', value: 'parsing' },
  { label: 'Indexed', value: 'indexed' },
  { label: 'Failed', value: 'failed' },
]

export function DocumentList() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | ''>('')
  const [viewing, setViewing] = useState<DocumentOut | null>(null)
  const { showToast } = useToast()

  const { data, isLoading, isError, error, isFetching } = useDocumentsList({
    page,
    page_size: PAGE_SIZE,
    status: statusFilter || undefined,
  })

  const deleteMutation = useDeleteDocument()
  const reprocessMutation = useReprocessDocument()

  const handleDelete = (doc: DocumentOut) => {
    if (!window.confirm(`Delete "${doc.original_filename}"? This cannot be undone.`)) return
    deleteMutation.mutate(doc.document_id, {
      onSuccess: () => showToast('Document deleted.', 'success'),
      onError: (err) => showToast(toUserMessage(err, 'Failed to delete document.'), 'error'),
    })
  }

  const handleReprocess = (doc: DocumentOut) => {
    reprocessMutation.mutate(doc.document_id, {
      onSuccess: () => showToast('Reprocessing started.', 'success'),
      onError: (err) => showToast(toUserMessage(err, 'Failed to start reprocessing.'), 'error'),
    })
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as DocumentStatus | '')
            setPage(1)
          }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
        >
          {STATUS_FILTERS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {data && (
          <span className="text-sm text-gray-400">
            {data.total} document{data.total === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorMessage error={error} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No documents yet"
          description="Upload a PDF above to start building your knowledge base."
        />
      ) : (
        <div className={`flex flex-col gap-2 transition-opacity ${isFetching ? 'opacity-60' : ''}`}>
          {data.items.map((doc) => (
            <DocumentCard
              key={doc.document_id}
              document={doc}
              onView={setViewing}
              onDelete={handleDelete}
              onReprocess={handleReprocess}
              isDeleting={deleteMutation.isPending && deleteMutation.variables === doc.document_id}
              isReprocessing={reprocessMutation.isPending && reprocessMutation.variables === doc.document_id}
            />
          ))}
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <ChevronLeft className="size-4" /> Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Next <ChevronRight className="size-4" />
          </button>
        </div>
      )}

      <Modal isOpen={Boolean(viewing)} onClose={() => setViewing(null)} title="Document details">
        {viewing && (
          <dl className="flex flex-col gap-2 text-sm">
            <Row label="Filename" value={viewing.original_filename} />
            <Row label="Type" value={viewing.document_type.toUpperCase()} />
            <Row label="Size" value={formatFileSize(viewing.file_size_bytes)} />
            <Row label="Status" value={viewing.status} />
            <Row label="Author" value={viewing.author ?? '—'} />
            <Row label="Uploaded" value={formatDate(viewing.created_at)} />
            <Row label="Last updated" value={formatDate(viewing.updated_at)} />
            <Row label="Document ID" value={viewing.document_id} mono />
            {viewing.error_message && <Row label="Error" value={viewing.error_message} />}
          </dl>
        )}
      </Modal>
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b border-gray-100 pb-2 last:border-0 dark:border-gray-700">
      <dt className="shrink-0 text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className={`truncate text-right text-gray-800 dark:text-gray-200 ${mono ? 'font-mono text-xs' : ''}`}>
        {value}
      </dd>
    </div>
  )
}
