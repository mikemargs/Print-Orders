import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheOrders, cachedOrders } from '../../offline/db'

const PAGE_SIZE = 250

async function loadStoreOrders(locationId: string) {
  const rows: WorkOrder[] = []
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const result = await apiFetch<{ orders: WorkOrder[] }>(
      `/api/orders?limit=${PAGE_SIZE}&offset=${offset}&location_id=${encodeURIComponent(locationId)}`,
    )
    rows.push(...result.orders)
    if (result.orders.length < PAGE_SIZE) break
  }
  await cacheOrders(rows)
  return rows
}

export function StoreDashboardPage() {
  const { session } = useSession()
  const { online } = useOnline()
  const locationId = session?.location.id ?? ''
  const orders = useQuery({
    queryKey: ['orders', 'store-dashboard', locationId, online],
    queryFn: async () => {
      if (!online) {
        return (await cachedOrders()).filter(order => !locationId || order.location_id === locationId)
      }
      return loadStoreOrders(locationId)
    },
  })

  const rows = orders.data ?? []
  const active = rows.filter(order => !['Completed', 'Cancelled'].includes(order.status))
  const ready = rows.filter(order => order.status === 'Ready for Pickup')
  const rush = active.filter(order => order.priority === 'Rush')
  const due = active
    .filter(order => order.due_date)
    .sort((a, b) => a.due_date.localeCompare(b.due_date))
    .slice(0, 12)

  return <section>
    <div className="page-heading">
      <div>
        <h1>Store Dashboard</h1>
        <p className="muted">
          {session?.location.name} #{session?.location.store_number} production overview
          {!online ? ' · cached' : ''}
        </p>
      </div>
      {online && <Link className="button" to="/orders/new">New work order</Link>}
    </div>

    <div className="metric-grid">
      <div className="metric"><span>Active</span><strong>{active.length}</strong></div>
      <div className="metric"><span>Rush</span><strong>{rush.length}</strong></div>
      <div className="metric"><span>Ready</span><strong>{ready.length}</strong></div>
      <div className="metric"><span>Total loaded</span><strong>{rows.length}</strong></div>
    </div>

    <div className="panel">
      <h2>Upcoming work</h2>
      {orders.isLoading
        ? <p>Loading…</p>
        : due.length
          ? <div className="table-wrap">
              <table>
                <thead><tr><th>Order</th><th>Status</th><th>Priority</th><th>Due</th><th>Description</th><th>Total</th></tr></thead>
                <tbody>{due.map(order => <tr key={order.id}>
                  <td><Link to={`/orders/${order.id}`}>{order.order_number}</Link></td>
                  <td>{order.status}</td>
                  <td><span className={`priority ${order.priority.toLowerCase()}`}>{order.priority}</span></td>
                  <td>{order.due_date}</td>
                  <td>{order.description || '—'}</td>
                  <td>${order.total.toFixed(2)}</td>
                </tr>)}</tbody>
              </table>
            </div>
          : <p className="muted">No upcoming work orders for this store.</p>}
    </div>
  </section>
}
