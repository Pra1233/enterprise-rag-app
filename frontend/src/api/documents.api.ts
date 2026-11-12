import type { DeleteResponse, DocumentListResponse, DocumentOut, ReprocessResponse } from '../types/document.types'
import { apiClient } from './axios'

export interface ListDocumentsParams {
  page?: number
  page_size?: number
  document_type?: string
  status?: string
}

export const documentsApi = {
  list: async (params: ListDocumentsParams = {}): Promise<DocumentListResponse> => {
    const { data } = await apiClient.get<DocumentListResponse>('/documents', { params })
    return data
  },

  get: async (documentId: string): Promise<DocumentOut> => {
    const { data } = await apiClient.get<DocumentOut>(`/documents/${documentId}`)
    return data
  },

  remove: async (documentId: string): Promise<DeleteResponse> => {
    const { data } = await apiClient.delete<DeleteResponse>(`/documents/${documentId}`)
    return data
  },

  reprocess: async (documentId: string): Promise<ReprocessResponse> => {
    const { data } = await apiClient.post<ReprocessResponse>(`/documents/${documentId}/reprocess`)
    return data
  },
}
