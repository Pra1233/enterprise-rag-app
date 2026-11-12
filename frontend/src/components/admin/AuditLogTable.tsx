import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

import { useAuditLog } from '../../hooks/useAdmin'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

export function AuditLogTable() {
  const [page, setPage] = useState(1)
  const pageSize = 20
  const { data, isLoading } = useAuditLog(page, pageSize)

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1

  if (isLoading && !data) {
    return <div className="py-8 text-center text-sm text-gray-500">Loading audit log…</div>
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800/50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Username</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Logged in at</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">IP</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">User agent</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Chat usage</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Upload usage</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {data?.items.map((entry) => (
              <tr key={entry.id}>
                <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{entry.username}</td>
                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
                  {formatDate(entry.logged_in_at)}
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">{entry.ip_address ?? '—'}</td>
                <td className="max-w-[16rem] truncate px-4 py-3 text-sm text-gray-500" title={entry.user_agent ?? ''}>
                  {entry.user_agent ?? '—'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
                  {entry.llm_requests_used}/{entry.llm_request_limit}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
                  {entry.uploads_used}/{entry.upload_limit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data && data.total > pageSize && (
        <div className="mt-3 flex items-center justify-between text-sm text-gray-500">
          <span>
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-md p-1.5 hover:bg-gray-100 disabled:opacity-40 dark:hover:bg-gray-800"
            >
              <ChevronLeft className="size-4" />
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="rounded-md p-1.5 hover:bg-gray-100 disabled:opacity-40 dark:hover:bg-gray-800"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
