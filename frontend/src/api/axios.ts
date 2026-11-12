import axios, { type AxiosError } from 'axios'

import { getApiBaseUrl } from '../config'
import { ApiError, type ApiErrorBody } from '../types/api.types'
import { clearAuthToken, getAuthToken } from './authToken'
import { maybeWarnFromHeaders } from './quotaWarning'

export const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30_000,
})

apiClient.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => {
    maybeWarnFromHeaders(response.headers as Record<string, unknown>)
    return response
  },
  (error: AxiosError<ApiErrorBody>) => {
    const status = error.response?.status ?? 0
    const body = error.response?.data

    if (status === 401) {
      clearAuthToken()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }

    if (body && typeof body === 'object' && 'error' in body) {
      return Promise.reject(new ApiError(status, body.error.code, body.error.message, body.error.request_id))
    }

    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new ApiError(0, 'TIMEOUT', 'The request timed out. Please try again.', ''))
    }

    if (!error.response) {
      return Promise.reject(
        new ApiError(0, 'NETWORK_ERROR', 'Could not reach the server. Is the backend running?', ''),
      )
    }

    return Promise.reject(new ApiError(status, 'UNKNOWN_ERROR', 'An unexpected error occurred.', ''))
  },
)
