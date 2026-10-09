import { ViewNotice, PageNavigation, useUrlValue, useListView } from '../../components/SummaryCard'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheOrders, cachedOrders } from '../../offline/db'
import { paymentStatus } from './paymentStatus'

function filterOrderView(rows:WorkOrder[],view:string){
 const pending=(o:WorkOrder)=>!['Completed','Cancelled'].includes(o.status)
 const today=new Date().toISOString().slice(0,10)
 return rows.filter(o=>view==='pending'?pending(o):view==='rush'?pending(o)&&o.priority==='Rush':view==='ready'?o.status==='Ready for Pickup':view==='overdue'?pending(o)&&!!o.due_date&&o.due_date<today:view==='outstanding'?o.balance>0:true)
}

export function OrdersPage() {
  const { session } = useSession()
  const { online } = useOnline()
  const {view,offset}=useListView()
  const [searchParams] = useSearchParams()
  const initialCustomerId = searchParams.get('customer_id') ?? ''
  const [search,setSearch]=useUrlValue('search','')
  const [status,setStatus]=useUrlValue('status','')
  const [priority,setPriority]=useUrlValue('priority','')
  const [customerId,setCustomerId]=useUrlValue('customer_id','')
  const [locationId,setLocationId]=useUrlValue('location_id',view||initialCustomerId?'':(session?.location.id??''))
  const [dueStart,setDueStart]=useUrlValue('due_start','')
  const [dueEnd,setDueEnd]=useUrlValue('due_end','')

  const query = useQuery({
    queryKey: ['orders',view,offset, search, status, priority, customerId, locationId, dueStart, dueEnd, online],
    queryFn: async () => {
      if (!online) {
        let rows = await cachedOrders()
        const needle = search.trim().toLowerCase()
        if (needle) {
          rows = rows.filter(order =>
            `${order.order_number} ${order.description}`.toLowerCase().includes(needle),
          )
        }
        if (customerId) rows = rows.filter(order => order.customer_id === customerId)
        if (status) rows = rows.filter(order => order.status === status)
        if (priority) rows = rows.filter(order => order.priority === priority)
        if (locationId) rows = rows.filter(order => order.location_id === locationId)
        if (dueStart) rows = rows.filter(order => order.due_date && order.due_date >= dueStart)
        if (dueEnd) rows = rows.filter(order => order.due_date && order.due_date <= dueEnd)
        rows=filterOrderView(rows,view)
        return {orders:rows.slice(offset,offset+250),total:rows.length}
      }

      const params = new URLSearchParams({ limit: '250',offset:String(offset) });if(view)params.set('view',view)
      if (search.trim()) params.set('search', search.trim())
      if (customerId) params.set('customer_id', customerId)
      if (status) params.set('status', status)
      if (priority) params.set('priority', priority)
      if (locationId) params.set('location_id', locationId)
      if (dueStart) params.set('due_start', dueStart)
      if (dueEnd) params.set('due_end', dueEnd)
      const result = await apiFetch<{ orders: WorkOrder[];total?:number }>(`/api/orders?${params}`)
      await cacheOrders(result.orders)
      return result
    },
  })

  return <section><ViewNotice/>
    <div className="page-heading">
      <div>
        <h1>Work Orders</h1>
        {!online && <p className="muted">Showing cached orders · read only</p>}
      </div>
      {online && <Link className="button" to={customerId ? `/orders/new?customer_id=${customerId}` : '/orders/new'}>New work order</Link>}
    </div>
    {customerId && <div className="notice">Customer filter is active. <button className="link-button" onClick={()=>setCustomerId('')}>Clear customer filter</button></div>}
    <div className="toolbar order-filters">
      <input placeholder="Search orders…" value={search} onChange={event => setSearch(event.target.value)} />
      <select aria-label="Store filter" value={locationId} onChange={event => setLocationId(event.target.value)}>
        <option value="">All stores</option>
        {session?.locations.map(location => <option key={location.id} value={location.id}>{location.name} #{location.store_number}</option>)}
      </select>
      <select aria-label="Status filter" value={status} onChange={event => setStatus(event.target.value)}>
        <option value="">All statuses</option>
        {['Quote','New','Awaiting Artwork','Proof Sent','Proof Approved','In Production','Ready for Pickup','Completed','On Hold','Cancelled'].map(value => <option key={value}>{value}</option>)}
      </select>
      <select aria-label="Priority filter" value={priority} onChange={event => setPriority(event.target.value)}>
        <option value="">All priorities</option><option>Normal</option><option>High</option><option>Rush</option>
      </select>
      <label className="compact-filter">Due from<input type="date" value={dueStart} onChange={event => setDueStart(event.target.value)} /></label>
      <label className="compact-filter">Due through<input type="date" value={dueEnd} onChange={event => setDueEnd(event.target.value)} /></label>
    </div>
    <div className="panel table-wrap">
      <table>
        <thead><tr><th>Order</th><th>Status</th><th>Priority</th><th>Due</th><th>Description</th><th>Artwork</th><th>Total</th><th>Payment</th><th>Balance</th></tr></thead>
        <tbody>{query.data?.orders.map(order => <tr key={order.id}>
          <td><Link to={`/orders/${order.id}`}>{order.order_number}</Link></td>
          <td>{order.status}</td>
          <td><span className={`priority ${order.priority.toLowerCase()}`}>{order.priority}</span></td>
          <td>{order.due_date}</td>
          <td>{order.description}</td>
          <td>
            {order.has_artwork === true
              ? <span className="artwork-status uploaded">Uploaded</span>
              : order.has_artwork === false
                ? <span className="artwork-status missing">Not Uploaded</span>
                : <span className="artwork-status unknown">Unknown</span>}
          </td>
          <td>${order.total.toFixed(2)}</td>
          <td>{paymentStatus(order)}</td>
          <td>${order.balance.toFixed(2)}</td>
        </tr>)}</tbody>
      </table>
      {!query.isLoading && !query.data?.orders.length && <p className="empty-state">No work orders found.</p>}
    </div>
    <PageNavigation total={query.data?.total} limit={250} count={query.data?.orders.length??0}/>
  </section>
}
