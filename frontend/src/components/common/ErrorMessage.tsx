import { AlertTriangle } from 'lucide-react'

import { ApiError } from '../../types/api.types'

interface ErrorMessageProps {
  error: unknown
  fallback?: string
}

/** Renders any caught error as a safe, user-facing message — never a stack trace. */
export function toUserMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'NETWORK_ERROR':
        return 'Could not reach the server. Please check your connection and try again.'
      case 'TIMEOUT':
        return 'The request took too long and timed out. Please try again.'
      case 'UNAUTHORIZED':
        return 'Your session has expired or is invalid. Please sign in again.'
      case 'FORBIDDEN':
        return "You don't have permission to do that."
      case 'NOT_FOUND':
        return 'That item could not be found.'
      case 'VECTOR_STORE_UNAVAILABLE':
        return 'The search index is temporarily unavailable. Please try again shortly.'
      case 'LLM_TIMEOUT':
        return 'The AI model took too long to respond. Please try again.'
      default:
        return error.message || fallback
    }
  }
  if (error instanceof Error) return error.message || fallback
  return fallback
}

export function ErrorMessage({ error, fallback }: ErrorMessageProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{toUserMessage(error, fallback)}</span>
    </div>
  )
}
