import { LogOut, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../components/common/Button'
import { getApiBaseUrl } from '../config'
import { useAuth } from '../context/AuthContext'

function UsageRow({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-gray-600 dark:text-gray-300">{label}</span>
        <span className="text-gray-500 dark:text-gray-400">
          {used} / {limit}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className={`h-full rounded-full ${pct >= 100 ? 'bg-red-500' : pct >= 80 ? 'bg-amber-500' : 'bg-brand-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-8 p-4 sm:p-6">
      <section className="glass-panel rounded-2xl p-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">Account</h2>
        <div className="mb-4 flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-gray-200 text-sm font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
            {user?.username.slice(0, 1).toUpperCase()}
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">{user?.username}</p>
            {user?.role === 'admin' ? (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400">
                <ShieldCheck className="size-3" /> Admin
              </span>
            ) : (
              <span className="text-xs text-gray-400">User</span>
            )}
          </div>
        </div>

        {user && (
          <div className="space-y-3">
            <UsageRow label="Chat messages" used={user.llm_requests_used} limit={user.llm_request_limit} />
            <UsageRow label="Document uploads" used={user.uploads_used} limit={user.upload_limit} />
          </div>
        )}

        <div className="mt-6">
          <Button variant="danger" icon={<LogOut className="size-4" />} onClick={handleLogout}>
            Log out
          </Button>
        </div>
      </section>

      <section>
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-gray-400">API connection</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Backend base URL:{' '}
          <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs dark:bg-gray-800">{getApiBaseUrl()}</code>
        </p>
      </section>
    </div>
  )
}
