import { SummaryCard } from '../../components/SummaryCard'
import { AssetsSummary } from '../assets/AssetsSummary'
import { OperationsSummary } from '../operations/OperationsSummary'
import { ShippingSummary } from '../shipping/ShippingSummary'
import { MailboxSummary } from '../mailboxes/MailboxSummary'
import { AttentionQueue } from './AttentionQueue'
import { TaskSummary } from '../tasks/TaskSummary'
import { IssueSummary } from '../issues/IssueSummary'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheOrders, cachedOrders } from '../../offline/db'

const PAGE_SIZE = 250
const closedStatuses = new Set(['Completed', 'Cancelled'])

async function loadAllOrders() {
  const rows: WorkOrder[] = []
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const result = await apiFetch<{ orders: WorkOrder[] }>(
      `/api/orders?limit=${PAGE_SIZE}&offset=${offset}`,
    )
    rows.push(...result.orders)
    if (result.orders.length < PAGE_SIZE) break
  }
  await cacheOrders(rows)
  return rows
}

export function DashboardPage() {
  const { session } = useSession()
  const { online } = useOnline()
  const orders = useQuery({
    queryKey: ['orders', 'main-dashboard', online],
    queryFn: async () => online ? loadAllOrders() : cachedOrders(),
  })

  const locationMap = new Map((session?.locations ?? []).map(location => [location.id, location]))
  const pending = (orders.data ?? [])
    .filter(order => !closedStatuses.has(order.status))
    .sort((a, b) => {
      if (!a.due_date && !b.due_date) return a.updated_at.localeCompare(b.updated_at)
      if (!a.due_date) return 1
      if (!b.due_date) return -1
      return a.due_date.localeCompare(b.due_date)
    })
  const rush = pending.filter(order => order.priority === 'Rush')
  const ready = pending.filter(order => order.status === 'Ready for Pickup')
  const today = new Date().toISOString().slice(0, 10)
  const overdue = pending.filter(order => order.due_date && order.due_date < today)

  const storeCounts = (session?.locations ?? []).map(location => ({
    ...location,
    count: pending.filter(order => order.location_id === location.id).length,
  }))

  return <section>
    <div className="page-heading">
      <div>
        <h1>Main Dashboard</h1>
        <p className="muted">
          All pending work across every location{!online ? ' · cached data' : ''}.
          {' '}Active working store: {session?.location.name} #{session?.location.store_number}
        </p>
      </div>
      {online && <Link className="button" to="/orders/new">New work order</Link>}
    </div>

    <div className="metric-grid">
      <SummaryCard to="/orders?view=pending&location_id="><span>Pending</span><strong>{pending.length}</strong></SummaryCard>
      <SummaryCard to="/orders?view=rush&location_id="><span>Rush</span><strong>{rush.length}</strong></SummaryCard>
      <SummaryCard to="/orders?view=ready&location_id="><span>Ready for pickup</span><strong>{ready.length}</strong></SummaryCard>
      <SummaryCard to="/orders?view=overdue&location_id="><span>Overdue</span><strong>{overdue.length}</strong></SummaryCard>
    </div>

    <AttentionQueue orders={pending}/>
    <OperationsSummary/>
    <AssetsSummary/>
    <MailboxSummary/>
    <ShippingSummary/>
    <TaskSummary/>
    <IssueSummary compact/>

    <div className="store-summary-grid" aria-label="Pending orders by store">
      {storeCounts.map(store => <Link key={store.id} className="store-summary-card" to={`/orders?view=pending&location_id=${store.id}`}>
        <span>{store.name} #{store.store_number}</span>
        <strong>{store.count}</strong>
        <small>pending order{store.count === 1 ? '' : 's'}</small>
      </Link>)}
    </div>

    <div className="panel">
      <div className="section-heading">
        <h2>All pending orders</h2>
        <span className="muted">{pending.length} total</span>
      </div>
      {orders.isLoading
        ? <p>Loading…</p>
        : pending.length
          ? <div className="table-wrap">
              <table>
                <thead><tr><th>Store</th><th>Order</th><th>Status</th><th>Priority</th><th>Due</th><th>Description</th><th>Total</th></tr></thead>
                <tbody>{pending.map(order => {
                  const location = locationMap.get(order.location_id)
                  return <tr key={order.id} className={order.due_date && order.due_date < today ? 'overdue-row' : undefined}>
                    <td>{location ? `${location.name} #${location.store_number}` : order.location_id}</td>
                    <td><Link to={`/orders/${order.id}`}>{order.order_number}</Link></td>
                    <td>{order.status}</td>
                    <td><span className={`priority ${order.priority.toLowerCase()}`}>{order.priority}</span></td>
                    <td>{order.due_date || '—'}</td>
                    <td>{order.description || '—'}</td>
                    <td>${order.total.toFixed(2)}</td>
                  </tr>
                })}</tbody>
              </table>
            </div>
          : <p className="empty-state">No pending work orders across any location.</p>}
    </div>
  </section>
}
