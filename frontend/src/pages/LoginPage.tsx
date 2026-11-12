import { motion } from 'framer-motion'
import { Check, Copy, LogIn, Sparkles } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { Button } from '../components/common/Button'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../types/api.types'

const DEMO_USERNAME = 'demo_user'
const DEMO_PASSWORD = 'demo123'

const TECH_STACK = [
  'FastAPI',
  'React 19',
  'PostgreSQL',
  'Qdrant',
  'Celery',
  'Groq LLM',
  'JWT Auth',
  'Tailwind v4',
]

const FEATURES = [
  'Retrieval-augmented chat with cited sources',
  'Async document ingestion (parse -> chunk -> embed -> index)',
  'Role-based access control with an admin panel',
  'Per-user usage quotas enforced server-side',
]

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [copied, setCopied] = useState(false)

  if (user) {
    return <Navigate to="/" replace />
  }

  const doLogin = async (u: string, p: string) => {
    setError(null)
    setIsSubmitting(true)
    try {
      await login(u, p)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to sign in. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    void doLogin(username, password)
  }

  const copyDemoCreds = async () => {
    try {
      await navigator.clipboard.writeText(`${DEMO_USERNAME} / ${DEMO_PASSWORD}`)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard API can fail (permissions/insecure context) — credentials
      // are already visible on screen, so this is a non-essential nicety.
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 px-4 py-10 dark:bg-gray-950">
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--color-brand-200),_transparent_60%)] opacity-60 dark:bg-[radial-gradient(ellipse_at_top,_var(--color-brand-900),_transparent_60%)] dark:opacity-40"
      />

      <div className="relative z-10 grid w-full max-w-5xl grid-cols-1 gap-10 lg:grid-cols-2 lg:items-center">
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="order-2 lg:order-1"
        >
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
            RAG Console
          </h1>
          <p className="mt-3 max-w-md text-base text-gray-600 dark:text-gray-300">
            An enterprise-style Retrieval-Augmented Generation system: upload PDFs, ask questions, and get
            cited answers grounded in your own documents.
          </p>

          <ul className="mt-6 space-y-2">
            {FEATURES.map((feature) => (
              <li key={feature} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-brand-500" />
                {feature}
              </li>
            ))}
          </ul>

          <div className="mt-6 flex flex-wrap gap-2">
            {TECH_STACK.map((tech) => (
              <span
                key={tech}
                className="rounded-full border border-gray-200 bg-white/70 px-3 py-1 text-xs font-medium text-gray-600 dark:border-gray-700 dark:bg-gray-900/50 dark:text-gray-300"
              >
                {tech}
              </span>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut', delay: 0.1 }}
          className="order-1 w-full max-w-md space-y-6 justify-self-center lg:order-2 lg:justify-self-end"
        >
        <div className="text-center lg:hidden">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">RAG Console</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Sign in to continue</p>
        </div>

        <div className="glass-panel rounded-2xl p-6 sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
                Username
              </label>
              <input
                id="username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-300 bg-white/80 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-gray-700 dark:bg-gray-900/60 dark:text-white"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-300 bg-white/80 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-gray-700 dark:bg-gray-900/60 dark:text-white"
              />
            </div>

            {error && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}

            <Button type="submit" isLoading={isSubmitting} icon={<LogIn className="size-4" />} className="w-full">
              Sign in
            </Button>
          </form>
        </div>

        <div className="glass-panel rounded-2xl border-brand-200 p-6 sm:p-8 dark:border-brand-800">
          <div className="mb-3 flex items-center gap-2 text-brand-700 dark:text-brand-300">
            <Sparkles className="size-5" />
            <h2 className="text-sm font-semibold uppercase tracking-wide">Demo Access</h2>
          </div>
          <p className="mb-4 text-sm text-gray-600 dark:text-gray-300">
            Exploring this as a portfolio piece? Jump straight in with a demo account — no sign-up needed.
          </p>

          <div className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white/70 px-3 py-2 dark:border-gray-700 dark:bg-gray-900/50">
            <code className="text-xs text-gray-700 dark:text-gray-200">
              {DEMO_USERNAME} / {DEMO_PASSWORD}
            </code>
            <button
              type="button"
              onClick={() => void copyDemoCreds()}
              aria-label="Copy demo credentials"
              className="shrink-0 rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200"
            >
              {copied ? <Check className="size-4 text-green-600" /> : <Copy className="size-4" />}
            </button>
          </div>

          <Button
            type="button"
            variant="secondary"
            isLoading={isSubmitting}
            onClick={() => void doLogin(DEMO_USERNAME, DEMO_PASSWORD)}
            className="w-full border-brand-300 text-brand-700 hover:bg-brand-50 dark:border-brand-700 dark:text-brand-300 dark:hover:bg-brand-950"
          >
            Continue as Demo User
          </Button>
        </div>
        </motion.div>
      </div>
    </div>
  )
}
