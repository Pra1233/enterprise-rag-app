import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { documentsApi, type ListDocumentsParams } from '../api/documents.api'

export const documentsQueryKeys = {
  all: ['documents'] as const,
  list: (params: ListDocumentsParams) => [...documentsQueryKeys.all, 'list', params] as const,
  detail: (id: string) => [...documentsQueryKeys.all, 'detail', id] as const,
}

export function useDocumentsList(params: ListDocumentsParams) {
  return useQuery({
    queryKey: documentsQueryKeys.list(params),
    queryFn: () => documentsApi.list(params),
    placeholderData: (previousData) => previousData,
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) => documentsApi.remove(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsQueryKeys.all })
    },
  })
}

export function useReprocessDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) => documentsApi.reprocess(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsQueryKeys.all })
    },
  })
}
