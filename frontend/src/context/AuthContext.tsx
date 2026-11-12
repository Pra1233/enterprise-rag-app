import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react'

import { authApi } from '../api/auth.api'
import { clearAuthToken, getAuthToken, setAuthToken } from '../api/authToken'
import type { AuthUser } from '../types/auth.types'

interface AuthContextValue {
  user: AuthUser | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!getAuthToken()) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      const me = await authApi.me()
      setUser(me)
    } catch {
      // axios 401 interceptor already clears the token / redirects; just
      // make sure local state agrees.
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(async (username: string, password: string) => {
    const response = await authApi.login(username, password)
    setAuthToken(response.access_token)
    setUser(response.user)
  }, [])

  const logout = useCallback(() => {
    clearAuthToken()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, refresh }}>{children}</AuthContext.Provider>
  )
}
