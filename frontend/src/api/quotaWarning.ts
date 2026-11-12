// Decouples axios (a plain module, no React context access) from the toast
// UI: a component inside ToastProvider's tree registers a handler here once,
// and axios.ts's response interceptor calls it whenever a response carries
// X-Quota-* headers showing usage at or above the warning threshold.

export interface QuotaWarning {
  resource: 'uploads' | 'llm_requests'
  used: number
  limit: number
}

const WARNING_THRESHOLD = 0.8

type Handler = (warning: QuotaWarning) => void

let handler: Handler | null = null

export function setQuotaWarningHandler(fn: Handler | null): void {
  handler = fn
}

export function maybeWarnFromHeaders(headers: Record<string, unknown>): void {
  const used = Number(headers['x-quota-used'])
  const limit = Number(headers['x-quota-limit'])
  const resource = headers['x-quota-resource'] as QuotaWarning['resource'] | undefined

  if (!resource || !Number.isFinite(used) || !Number.isFinite(limit) || limit <= 0) {
    return
  }
  if (used / limit >= WARNING_THRESHOLD) {
    handler?.({ resource, used, limit })
  }
}
