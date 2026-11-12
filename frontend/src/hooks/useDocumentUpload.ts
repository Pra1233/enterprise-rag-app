import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { ingestionApi } from '../api/ingestion.api'
import { toUserMessage } from '../components/common/ErrorMessage'
import type { DocumentStatus } from '../types/document.types'
import { documentsQueryKeys } from './useDocuments'

export interface UploadItem {
  id: string
  fileName: string
  uploadProgress: number
  documentId?: string
  taskId?: string
  status: DocumentStatus | 'uploading' | 'upload_failed'
  stage: DocumentStatus | null
  error?: string
}

const POLL_INTERVAL_MS = 2000
const TERMINAL_STATUSES = new Set<DocumentStatus>(['indexed', 'failed'])

export function useDocumentUpload() {
  const [items, setItems] = useState<UploadItem[]>([])
  const pollTimers = useRef<Map<string, number>>(new Map())
  const queryClient = useQueryClient()

  useEffect(() => {
    const timers = pollTimers.current
    return () => {
      timers.forEach((timer) => window.clearInterval(timer))
      timers.clear()
    }
  }, [])

  const updateItem = useCallback((localId: string, patch: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.id === localId ? { ...it, ...patch } : it)))
  }, [])

  const stopPolling = useCallback((localId: string) => {
    const timer = pollTimers.current.get(localId)
    if (timer) {
      window.clearInterval(timer)
      pollTimers.current.delete(localId)
    }
  }, [])

  const pollStatus = useCallback(
    (localId: string, taskId: string) => {
      const timer = window.setInterval(async () => {
        try {
          const status = await ingestionApi.getStatus(taskId)
          updateItem(localId, { status: status.status, stage: status.stage, error: status.error ?? undefined })
          if (TERMINAL_STATUSES.has(status.status)) {
            stopPolling(localId)
            queryClient.invalidateQueries({ queryKey: documentsQueryKeys.all })
          }
        } catch (err) {
          // A single failed poll is transient (network blip); keep retrying
          // rather than flipping the whole upload to a false "failed" state.
          console.error('Ingestion status poll failed', err)
        }
      }, POLL_INTERVAL_MS)
      pollTimers.current.set(localId, timer)
    },
    [updateItem, stopPolling, queryClient],
  )

  const uploadFile = useCallback(
    async (file: File, author?: string) => {
      const localId = crypto.randomUUID()
      setItems((prev) => [
        ...prev,
        { id: localId, fileName: file.name, uploadProgress: 0, status: 'uploading', stage: null },
      ])

      try {
        const response = await ingestionApi.upload(file, author, (percent) => {
          updateItem(localId, { uploadProgress: percent })
        })
        updateItem(localId, {
          documentId: response.document_id,
          taskId: response.task_id,
          status: 'queued',
          uploadProgress: 100,
        })
        queryClient.invalidateQueries({ queryKey: documentsQueryKeys.all })
        pollStatus(localId, response.task_id)
      } catch (err) {
        updateItem(localId, { status: 'upload_failed', error: toUserMessage(err, 'Upload failed.') })
      }
    },
    [updateItem, pollStatus, queryClient],
  )

  const dismissItem = useCallback(
    (localId: string) => {
      stopPolling(localId)
      setItems((prev) => prev.filter((it) => it.id !== localId))
    },
    [stopPolling],
  )

  return { items, uploadFile, dismissItem }
}
