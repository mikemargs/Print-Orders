import { beforeEach, describe, expect, it } from 'vitest'
import {
  cacheSessionInfo,
  cachedSessionInfo,
  clearOfflineCache,
  pendingLogoutCsrf,
  setPendingLogoutCsrf,
} from './db'
import type { SessionInfo } from '../api/types'

const session: SessionInfo = {
  csrf_token: 'deferred-logout-csrf',
  company: { id: 'c', name: 'Print Co', code: 'PRINT' },
  employee: { id: 'e', name: 'Alex', role: 'employee', location_ids: ['l'], active: true },
  location: { id: 'l', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
  locations: [{ id: 'l', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true }],
}

describe('offline session metadata', () => {
  beforeEach(clearOfflineCache)

  it('caches non-secret session metadata needed for offline recovery/logout', async () => {
    await cacheSessionInfo(session)
    const cached = await cachedSessionInfo()
    expect(cached?.employee.name).toBe('Alex')
    expect(cached?.csrf_token).toBe('deferred-logout-csrf')
  })

  it('can retain a pending logout CSRF value after the ordinary cache is cleared', async () => {
    await clearOfflineCache()
    await setPendingLogoutCsrf('logout-csrf')
    expect(await pendingLogoutCsrf()).toBe('logout-csrf')
  })
})
