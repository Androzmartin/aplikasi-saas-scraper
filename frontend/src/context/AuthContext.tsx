import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, clearToken, getToken, setToken } from '@/api/client'
import type { Tenant, User } from '@/api/types'

interface AuthState {
  user: User | null
  tenant: Tenant | null
  loading: boolean
  isAdmin: boolean
  login: (email: string, password: string) => Promise<void>
  register: (data: { company_name: string; name: string; email: string; password: string }) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setTenant(null)
      setLoading(false)
      return
    }
    try {
      const me = await api.me()
      setUser(me.user)
      setTenant(me.tenant)
    } catch {
      clearToken()
      setUser(null)
      setTenant(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // The API client raises this when a request comes back 401.
  useEffect(() => {
    const onExpired = () => {
      setUser(null)
      setTenant(null)
    }
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const token = await api.login(email, password)
    setToken(token.access_token)
    setLoading(true)
    await refresh()
  }, [refresh])

  const register = useCallback(
    async (data: { company_name: string; name: string; email: string; password: string }) => {
      const token = await api.register(data)
      setToken(token.access_token)
      setLoading(true)
      await refresh()
    },
    [refresh],
  )

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* the token is discarded either way */
    }
    clearToken()
    setUser(null)
    setTenant(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user, tenant, loading, isAdmin: user?.role === 'admin_internal',
      login, register, logout, refresh,
    }),
    [user, tenant, loading, login, register, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
