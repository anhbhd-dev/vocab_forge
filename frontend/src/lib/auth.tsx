import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, getToken, setToken } from './api'
import type { User } from './types'

interface AuthValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      setUser(await api.me())
    } catch {
      // Token hỏng/hết hạn: api.ts đã xoá token, chỉ cần về trạng thái chưa đăng nhập.
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const value = useMemo<AuthValue>(
    () => ({
      user,
      loading,
      refresh,
      login: async (email, password) => {
        const { access_token } = await api.login(email, password)
        setToken(access_token)
        setUser(await api.me())
      },
      register: async (email, password) => {
        const { access_token } = await api.register(email, password)
        setToken(access_token)
        setUser(await api.me())
      },
      logout: () => {
        setToken(null)
        setUser(null)
      },
    }),
    [user, loading, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth phải nằm trong <AuthProvider>')
  return value
}
