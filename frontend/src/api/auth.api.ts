import type { AuthUser, LoginResponse } from '../types/auth.types'
import { apiClient } from './axios'

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', { username, password })
    return data
  },

  me: async (): Promise<AuthUser> => {
    const { data } = await apiClient.get<AuthUser>('/auth/me')
    return data
  },
}
