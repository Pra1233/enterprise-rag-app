import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { adminApi } from '../api/admin.api'
import type { CreateUserPayload, UpdateUserPayload } from '../types/admin.types'

export const adminQueryKeys = {
  all: ['admin'] as const,
  users: () => [...adminQueryKeys.all, 'users'] as const,
  auditLog: (page: number, pageSize: number) => [...adminQueryKeys.all, 'audit-log', page, pageSize] as const,
}

export function useAdminUsers() {
  return useQuery({
    queryKey: adminQueryKeys.users(),
    queryFn: () => adminApi.listUsers(),
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateUserPayload) => adminApi.createUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() })
    },
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: UpdateUserPayload }) =>
      adminApi.updateUser(userId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() })
    },
  })
}

export function useAuditLog(page: number, pageSize = 20) {
  return useQuery({
    queryKey: adminQueryKeys.auditLog(page, pageSize),
    queryFn: () => adminApi.auditLog(page, pageSize),
    placeholderData: (previousData) => previousData,
  })
}
