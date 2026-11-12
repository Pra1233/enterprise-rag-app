import { useEffect } from 'react'

import { setQuotaWarningHandler } from '../../api/quotaWarning'
import { useToast } from './ToastProvider'

const RESOURCE_LABEL: Record<string, string> = {
  uploads: 'document upload',
  llm_requests: 'chat message',
}

/** Mounted once inside ToastProvider's tree — bridges the plain axios module
 * (no React context access) to the toast UI for proactive "approaching your
 * quota" warnings. Renders nothing. */
export function QuotaWarningListener() {
  const { showToast } = useToast()

  useEffect(() => {
    setQuotaWarningHandler(({ resource, used, limit }) => {
      const label = RESOURCE_LABEL[resource] ?? resource
      showToast(`You've used ${used} of ${limit} ${label}s. Contact an admin if you need a higher limit.`, 'warning')
    })
    return () => setQuotaWarningHandler(null)
  }, [showToast])

  return null
}
