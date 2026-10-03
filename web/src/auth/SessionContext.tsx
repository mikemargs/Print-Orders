import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ApiError, apiFetch, clearCsrfToken, getCsrfToken, setCsrfToken } from '../api/http'
import type { SessionInfo } from '../api/types'
import {
  cacheSessionInfo,
  cachedSessionInfo,
  clearOfflineCache,
  clearPendingLogout,
  pendingLogoutCsrf,
  setPendingLogoutCsrf,
} from '../offline/db'

type SessionState = {
  session: SessionInfo | null
  loading: boolean
  refresh: () => Promise<void>
  setSession: (session: SessionInfo) => void
  logout: (clearCache?: boolean) => Promise<void>
}

const Context = createContext<SessionState | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<SessionInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const mounted = useRef(true)

  const setSession = useCallback((next: SessionInfo) => {
    if (!mounted.current) return
    setCsrfToken(next.csrf_token)
    setSessionState(next)
    void cacheSessionInfo(next)
  }, [])

  const finishPendingLogout = useCallback(async () => {
    const pending = await pendingLogoutCsrf()
    if (!pending) return false

    // A queued sign-out always wins over a cached session. Stay signed out while
    // offline and retry clearing the HttpOnly server cookie when connectivity returns.
    if (!navigator.onLine) return true

    setCsrfToken(pending)
    try {
      await apiFetch<{ ok: boolean }>('/api/web/auth/logout', { method: 'POST' })
      await clearPendingLogout()
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        // The server session is already unusable, which is equivalent to logout.
        await clearPendingLogout()
      } else {
        clearCsrfToken()
        setSessionState(null)
        return true
      }
    }
    clearCsrfToken()
    if (mounted.current) setSessionState(null)
    return true
  }, [])

  const refresh = useCallback(async () => {
    try {
      if (await finishPendingLogout()) {
        if (mounted.current) setSessionState(null)
        return
      }
      setSession(await apiFetch<SessionInfo>('/api/web/session'))
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        clearCsrfToken()
        if (mounted.current) setSessionState(null)
        await clearOfflineCache()
      } else if (
        !navigator.onLine ||
        (error instanceof ApiError && (error.status === 0 || error.status >= 500))
      ) {
        const cached = await cachedSessionInfo()
        if (cached) {
          if (mounted.current) {
            setCsrfToken(cached.csrf_token)
            setSessionState(cached)
          }
        } else {
          clearCsrfToken()
          if (mounted.current) setSessionState(null)
        }
      } else {
        throw error
      }
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [finishPendingLogout, setSession])

  const logout = useCallback(async (clearCache = true) => {
    const csrf = session?.csrf_token || getCsrfToken()
    let deferServerLogout = !navigator.onLine

    if (navigator.onLine) {
      try {
        await apiFetch<{ ok: boolean }>('/api/web/auth/logout', { method: 'POST' })
      } catch (error) {
        if (!(error instanceof ApiError) || ![401, 403].includes(error.status)) {
          deferServerLogout = true
        }
      }
    }

    clearCsrfToken()
    if (mounted.current) setSessionState(null)
    if (clearCache) await clearOfflineCache()
    if (deferServerLogout && csrf) await setPendingLogoutCsrf(csrf)
  }, [session])

  useEffect(() => {
    mounted.current = true
    void refresh()
    const onOnline = () => void refresh()
    window.addEventListener('online', onOnline)
    return () => {
      mounted.current = false
      window.removeEventListener('online', onOnline)
    }
  }, [refresh])

  const value = useMemo(
    () => ({ session, loading, refresh, setSession, logout }),
    [session, loading, refresh, setSession, logout],
  )
  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useSession() {
  const value = useContext(Context)
  if (!value) throw new Error('useSession must be inside SessionProvider')
  return value
}
