import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheOrders, cachedOrders } from '../../offline/db'

export function DashboardPage() {
  const { session } = useSession(); const {online}=useOnline()
  const orders = useQuery({ queryKey: ['orders','dashboard',session?.location.id,online], queryFn: async()=>{const locationId=session?.location.id??'';if(!online)return {orders:(await cachedOrders()).filter(order=>!locationId||order.location_id===locationId)};const result=await apiFetch<{orders:WorkOrder[]}>(`/api/orders?limit=100&location_id=${encodeURIComponent(locationId)}`);await cacheOrders(result.orders);return result} })
  const rows = orders.data?.orders ?? []
  const active = rows.filter(o => !['Completed','Cancelled'].includes(o.status))
  const ready = rows.filter(o => o.status === 'Ready for Pickup')
  const rush = active.filter(o => o.priority === 'Rush')
  const due = active.filter(o => o.due_date).sort((a,b) => a.due_date.localeCompare(b.due_date)).slice(0,8)
  return <section>
    <div className="page-heading"><div><h1>Dashboard</h1><p className="muted">{session?.location.name} production overview{!online?' · cached':''}</p></div>{online&&<Link className="button" to="/orders/new">New work order</Link>}</div>
    <div className="metric-grid"><div className="metric"><span>Active</span><strong>{active.length}</strong></div><div className="metric"><span>Rush</span><strong>{rush.length}</strong></div><div className="metric"><span>Ready</span><strong>{ready.length}</strong></div><div className="metric"><span>Total loaded</span><strong>{rows.length}</strong></div></div>
    <div className="panel"><h2>Upcoming work</h2>{orders.isLoading ? <p>Loading…</p> : due.length ? <div className="table-wrap"><table><thead><tr><th>Order</th><th>Status</th><th>Priority</th><th>Due</th><th>Total</th></tr></thead><tbody>{due.map(o => <tr key={o.id}><td><Link to={`/orders/${o.id}`}>{o.order_number}</Link></td><td>{o.status}</td><td>{o.priority}</td><td>{o.due_date}</td><td>${o.total.toFixed(2)}</td></tr>)}</tbody></table></div> : <p className="muted">No upcoming work orders.</p>}</div>
  </section>
}
