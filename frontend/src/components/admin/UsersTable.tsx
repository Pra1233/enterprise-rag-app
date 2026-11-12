import { Pencil, ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import { useAdminUsers, useCreateUser, useUpdateUser } from '../../hooks/useAdmin'
import type { AdminUser } from '../../types/admin.types'
import { useToast } from '../common/ToastProvider'
import { UserFormDialog } from './UserFormDialog'

function UsageBar({ used, limit }: { used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0
  return (
    <div className="w-28">
      <div className="mb-0.5 text-xs text-gray-500 dark:text-gray-400">
        {used}/{limit}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className={`h-full rounded-full ${pct >= 100 ? 'bg-red-500' : pct >= 80 ? 'bg-amber-500' : 'bg-brand-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function UsersTable() {
  const { data: users, isLoading } = useAdminUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const { showToast } = useToast()

  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<AdminUser | undefined>(undefined)

  const openCreate = () => {
    setEditingUser(undefined)
    setIsDialogOpen(true)
  }

  const openEdit = (user: AdminUser) => {
    setEditingUser(user)
    setIsDialogOpen(true)
  }

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-gray-500">Loading users…</div>
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">{users?.length ?? 0} users</h2>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          + Create user
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800/50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Username</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Role</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Chat usage</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Upload usage</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">Active</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {users?.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{u.username}</td>
                <td className="px-4 py-3">
                  {u.role === 'admin' ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                      <ShieldCheck className="size-3" /> Admin
                    </span>
                  ) : (
                    <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                      User
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <UsageBar used={u.llm_requests_used} limit={u.llm_request_limit} />
                </td>
                <td className="px-4 py-3">
                  <UsageBar used={u.uploads_used} limit={u.upload_limit} />
                </td>
                <td className="px-4 py-3 text-sm">
                  {u.is_active ? (
                    <span className="text-green-600 dark:text-green-400">Active</span>
                  ) : (
                    <span className="text-gray-400">Disabled</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => openEdit(u)}
                    aria-label={`Edit ${u.username}`}
                    className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700"
                  >
                    <Pencil className="size-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <UserFormDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        user={editingUser}
        isSubmitting={createUser.isPending || updateUser.isPending}
        onCreate={async (payload) => {
          await createUser.mutateAsync(payload)
          showToast(`User '${payload.username}' created.`)
        }}
        onUpdate={async (userId, payload) => {
          await updateUser.mutateAsync({ userId, payload })
          showToast('User updated.')
        }}
      />
    </div>
  )
}
