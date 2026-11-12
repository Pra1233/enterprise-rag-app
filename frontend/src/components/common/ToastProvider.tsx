import { AlertTriangle, CheckCircle2, X, XCircle } from 'lucide-react'
import { createContext, type ReactNode, useCallback, useContext, useState } from 'react'

interface Toast {
  id: string
  message: string
  type: 'success' | 'error' | 'warning'
}

interface ToastContextValue {
  showToast: (message: string, type?: Toast['type']) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, type: Toast['type'] = 'success') => {
      const id = crypto.randomUUID()
      setToasts((prev) => [...prev, { id, message, type }])
      window.setTimeout(() => dismiss(id), 5000)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`pointer-events-auto flex items-center gap-2 rounded-lg border px-4 py-3 text-sm shadow-lg ${
              toast.type === 'success'
                ? 'border-green-200 bg-white text-green-800 dark:border-green-900 dark:bg-gray-800 dark:text-green-300'
                : toast.type === 'warning'
                  ? 'border-amber-200 bg-white text-amber-800 dark:border-amber-900 dark:bg-gray-800 dark:text-amber-300'
                  : 'border-red-200 bg-white text-red-800 dark:border-red-900 dark:bg-gray-800 dark:text-red-300'
            }`}
          >
            {toast.type === 'success' ? (
              <CheckCircle2 className="size-4 shrink-0" />
            ) : toast.type === 'warning' ? (
              <AlertTriangle className="size-4 shrink-0" />
            ) : (
              <XCircle className="size-4 shrink-0" />
            )}
            <span>{toast.message}</span>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="ml-2 text-gray-400 hover:text-gray-600"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
