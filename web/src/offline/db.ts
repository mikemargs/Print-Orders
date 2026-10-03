import Dexie, { type Table } from 'dexie'
import type { Customer, SessionInfo, WorkOrder } from '../api/types'

export interface Cached<T> { id: string; value: T; cached_at: string }
export type CachedSessionInfo = SessionInfo

const MAX_CACHED_ORDERS = 1000
const MAX_CACHED_CUSTOMERS = 500

class PrintOrdersDB extends Dexie {
  customers!: Table<Cached<Customer>, string>
  orders!: Table<Cached<WorkOrder>, string>
  meta!: Table<{ key: string; value: string }, string>
  constructor() {
    super('PrintOrderManagerWeb')
    this.version(1).stores({ customers: 'id,cached_at', orders: 'id,cached_at', meta: 'key' })
  }
}
export const offlineDB = new PrintOrdersDB()

async function prune<T>(table: Table<Cached<T>, string>, maxRows: number) {
  const count = await table.count()
  if (count <= maxRows) return
  const keys = await table.orderBy('cached_at').limit(count - maxRows).primaryKeys()
  await table.bulkDelete(keys as string[])
}

async function noteSync(now: string) {
  await offlineDB.meta.put({ key: 'last_sync', value: now })
  window.dispatchEvent(new CustomEvent('printorders-cache-updated', { detail: now }))
}

export async function cacheCustomers(items: Customer[]) {
  const now = new Date().toISOString()
  await offlineDB.transaction('rw', offlineDB.customers, offlineDB.meta, async () => {
    await offlineDB.customers.bulkPut(items.map(value => ({ id: value.id, value, cached_at: now })))
    await prune(offlineDB.customers, MAX_CACHED_CUSTOMERS)
    await noteSync(now)
  })
}

export async function cacheOrders(items: WorkOrder[]) {
  const now = new Date().toISOString()
  await offlineDB.transaction('rw', offlineDB.orders, offlineDB.meta, async () => {
    await offlineDB.orders.bulkPut(items.map(value => ({ id: value.id, value, cached_at: now })))
    await prune(offlineDB.orders, MAX_CACHED_ORDERS)
    await noteSync(now)
  })
}

export async function cachedCustomers() { return (await offlineDB.customers.toArray()).map(x => x.value) }
export async function cachedOrders() { return (await offlineDB.orders.toArray()).map(x => x.value) }
export async function cachedCustomer(id: string) { return (await offlineDB.customers.get(id))?.value }
export async function cachedOrder(id: string) { return (await offlineDB.orders.get(id))?.value }
export async function lastSync() { return (await offlineDB.meta.get('last_sync'))?.value || '' }

export async function cacheSessionInfo(session: SessionInfo) {
  // The CSRF token is deliberately non-secret session metadata. Keeping it in
  // origin-scoped IndexedDB lets an offline sign-out be completed against the
  // HttpOnly server session once connectivity returns; the session cookie itself
  // is never exposed to JavaScript or cached here.
  await offlineDB.transaction('rw', offlineDB.customers, offlineDB.orders, offlineDB.meta, async () => {
    const previous = await offlineDB.meta.get('session_context')
    if (previous) {
      try {
        const prior = JSON.parse(previous.value) as CachedSessionInfo
        if (prior.company.id !== session.company.id || prior.employee.id !== session.employee.id) {
          await offlineDB.customers.clear()
          await offlineDB.orders.clear()
          await offlineDB.meta.delete('last_sync')
        }
      } catch {
        await offlineDB.customers.clear()
        await offlineDB.orders.clear()
        await offlineDB.meta.delete('last_sync')
      }
    }
    await offlineDB.meta.put({ key: 'session_context', value: JSON.stringify(session) })
  })
}

export async function cachedSessionInfo(): Promise<CachedSessionInfo | null> {
  const raw = (await offlineDB.meta.get('session_context'))?.value
  if (!raw) return null
  try { return JSON.parse(raw) as CachedSessionInfo } catch { return null }
}

export async function clearCachedSessionInfo() { await offlineDB.meta.delete('session_context') }
export async function clearOfflineCache() {
  await offlineDB.transaction('rw', offlineDB.customers, offlineDB.orders, offlineDB.meta, async () => {
    await offlineDB.customers.clear()
    await offlineDB.orders.clear()
    await offlineDB.meta.clear()
  })
}
export async function setPendingLogoutCsrf(csrf: string) { await offlineDB.meta.put({ key: 'pending_logout_csrf', value: csrf }) }
export async function pendingLogoutCsrf() { return (await offlineDB.meta.get('pending_logout_csrf'))?.value || '' }
export async function clearPendingLogout() { await offlineDB.meta.delete('pending_logout_csrf') }
