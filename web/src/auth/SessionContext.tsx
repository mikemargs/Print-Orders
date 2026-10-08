import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
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
  switchLocation: (locationId: string) => Promise<void>
  logout: (clearCache?: boolean) => Promise<void>
}

const Context = createContext<SessionState | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<SessionInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const mounted = useRef(true)
  const queryClient = useQueryClient()
  const identity = useRef('')
  const authGeneration = useRef(0)
  const signingOut = useRef(false)
  const pendingStoreSwitch = useRef<Promise<SessionInfo> | null>(null)
  const clearIssueQueries = useCallback(() => {
    void queryClient.cancelQueries({ queryKey: ['issues'] })
    queryClient.removeQueries({ queryKey: ['issues'] })
  }, [queryClient])

  const setSession = useCallback((next: SessionInfo) => {
    if (!mounted.current) return
    authGeneration.current += 1
    const nextIdentity = `${next.company.id}:${next.employee.id}`
    if (identity.current !== nextIdentity) clearIssueQueries()
    identity.current = nextIdentity
    setCsrfToken(next.csrf_token)
    setSessionState(next)
    void cacheSessionInfo(next)
  }, [clearIssueQueries])

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
    clearIssueQueries()
    identity.current = ''
    if (mounted.current) setSessionState(null)
    return true
  }, [clearIssueQueries])

  const refresh = useCallback(async () => {
    if (signingOut.current) return
    const generation = authGeneration.current
    try {
      if (await finishPendingLogout()) {
        if (mounted.current) setSessionState(null)
        return
      }
      const next = await apiFetch<SessionInfo>('/api/web/session')
      if (generation !== authGeneration.current || signingOut.current) return
      setSession(next)
    } catch (error) {
      if (generation !== authGeneration.current || signingOut.current) return
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        clearCsrfToken()
        clearIssueQueries()
        identity.current = ''
        if (mounted.current) setSessionState(null)
        await clearOfflineCache()
      } else if (
        !navigator.onLine ||
        (error instanceof ApiError && (error.status === 0 || error.status >= 500))
      ) {
        const cached = await cachedSessionInfo()
        if (generation !== authGeneration.current || signingOut.current) return
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
  }, [finishPendingLogout, setSession, clearIssueQueries])

  const switchLocation = useCallback(async (locationId: string) => {
    if (!navigator.onLine) throw new Error('Store switching requires an online connection')
    if (signingOut.current || pendingStoreSwitch.current) throw new Error('A session change is already in progress')
    const generation = authGeneration.current
    const request = apiFetch<SessionInfo>('/api/web/auth/location', {
      method: 'POST',
      body: JSON.stringify({ location_id: locationId }),
    })
    pendingStoreSwitch.current = request
    try {
      const next = await request
      if (generation !== authGeneration.current || signingOut.current) return
      setSession(next)
    } finally {
      pendingStoreSwitch.current = null
    }
  }, [setSession])

  const logout = useCallback(async (clearCache = true) => {
    if (signingOut.current) return
    signingOut.current = true
    authGeneration.current += 1
    // A location response rotates the HttpOnly cookie. Let it settle before
    // logout clears that cookie, and ignore its now-stale session state.
    let switched: SessionInfo | null = null
    try { switched = await pendingStoreSwitch.current } catch { /* still log out */ }
    const csrf = switched?.csrf_token || session?.csrf_token || getCsrfToken()
    let deferServerLogout = !navigator.onLine

    if (navigator.onLine) {
      if (csrf) setCsrfToken(csrf)
      try {
        await apiFetch<{ ok: boolean }>('/api/web/auth/logout', { method: 'POST' })
      } catch (error) {
        if (!(error instanceof ApiError) || ![401, 403].includes(error.status)) {
          deferServerLogout = true
        }
      }
    }

    clearCsrfToken()
    clearIssueQueries()
    identity.current = ''
    // Persist the logout before exposing the login form or allowing a reload.
    if (clearCache) await clearOfflineCache()
    if (deferServerLogout && csrf) await setPendingLogoutCsrf(csrf)
    if (mounted.current) setSessionState(null)
    signingOut.current = false
  }, [session, clearIssueQueries])

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
    () => ({ session, loading, refresh, setSession, switchLocation, logout }),
    [session, loading, refresh, setSession, switchLocation, logout],
  )
  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useSession() {
  const value = useContext(Context)
  if (!value) throw new Error('useSession must be inside SessionProvider')
  return value
}
