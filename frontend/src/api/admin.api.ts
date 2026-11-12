import type {
  AdminUser,
  AuditLogResponse,
  CreateUserPayload,
  UpdateUserPayload,
} from '../types/admin.types'
import { apiClient } from './axios'

export const adminApi = {
  listUsers: async (): Promise<AdminUser[]> => {
    const { data } = await apiClient.get<AdminUser[]>('/admin/users')
    return data
  },

  createUser: async (payload: CreateUserPayload): Promise<AdminUser> => {
    const { data } = await apiClient.post<AdminUser>('/admin/users', payload)
    return data
  },

  updateUser: async (userId: string, payload: UpdateUserPayload): Promise<AdminUser> => {
    const { data } = await apiClient.patch<AdminUser>(`/admin/users/${userId}`, payload)
    return data
  },

  auditLog: async (page = 1, pageSize = 20): Promise<AuditLogResponse> => {
    const { data } = await apiClient.get<AuditLogResponse>('/admin/audit-log', {
      params: { page, page_size: pageSize },
    })
    return data
  },
}
