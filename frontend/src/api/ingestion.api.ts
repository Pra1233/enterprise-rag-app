import type { IngestionStatusResponse, UploadResponse } from '../types/document.types'
import { apiClient } from './axios'

export const ingestionApi = {
  upload: async (
    file: File,
    author: string | undefined,
    onProgress?: (percent: number) => void,
  ): Promise<UploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    if (author) formData.append('author', author)

    const { data } = await apiClient.post<UploadResponse>('/ingestion/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // Longer than the global default: on a free-tier deploy with no
      // background worker (CELERY_TASK_ALWAYS_EAGER=true), this request
      // blocks until ingestion actually finishes, not just until it's queued.
      timeout: 120_000,
      onUploadProgress: (event) => {
        if (onProgress && event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    })
    return data
  },

  getStatus: async (taskId: string): Promise<IngestionStatusResponse> => {
    const { data } = await apiClient.get<IngestionStatusResponse>(`/ingestion/status/${taskId}`)
    return data
  },
}
