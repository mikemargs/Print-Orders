import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import { listIssues } from '../../api/issues'
import { listMailboxes } from '../../api/mailboxes'
import { listTasks } from '../../api/tasks'
import { listShippingCases } from '../../api/shipping'
import type { Customer, WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cacheOrders, cachedCustomer, cachedOrders } from '../../offline/db'

function displayName(customer: Customer) {
  return customer.company || `${customer.first_name} ${customer.last_name}`.trim() || 'Unnamed customer'
}

export function CustomerProfile() {
  const { id } = useParams()
  const { session } = useSession()
  const { online } = useOnline()

  const customer = useQuery({
    queryKey: ['customer-profile', id, online],
    enabled: Boolean(id),
    queryFn: async () => {
      if (!id) throw new Error('Customer missing')
      if (!online) {
        const row = await cachedCustomer(id)
        if (!row) throw new Error('Customer is not cached on this device')
        return row
      }
      const row = await apiFetch<Customer>(`/api/customers/${id}`)
      await cacheCustomers([row])
      return row
    },
  })

  const orders = useQuery({
    queryKey: ['customer-profile-orders', id, online],
    enabled: Boolean(id),
    queryFn: async () => {
      if (!id) return [] as WorkOrder[]
      if (!online) return (await cachedOrders()).filter(order => order.customer_id === id)
      const result = await apiFetch<{ orders: WorkOrder[] }>(`/api/orders?customer_id=${encodeURIComponent(id)}&limit=250`)
      await cacheOrders(result.orders)
      return result.orders
    },
  })

  const issues = useQuery({
    queryKey: ['customer-profile-issues', id],
    enabled: Boolean(id) && online,
    queryFn: () => listIssues({ customer_id: id, limit: 250, offset: 0 }),
  })

  const tasks = useQuery({
    queryKey: ['customer-profile-tasks', id],
    enabled: Boolean(id) && online,
    queryFn: () => listTasks({ customer_id: id, open_only: false, limit: 250 }),
  })

  const mailboxes = useQuery({
    queryKey: ['customer-profile-mailboxes', id],
    enabled: Boolean(id) && online,
    queryFn: () => listMailboxes({ customer_id: id, limit: 250 }),
  })

  const shipping = useQuery({
    queryKey: ['customer-profile-shipping', id],
    enabled: Boolean(id) && online,
    queryFn: () => listShippingCases({ customer_id: id, open_only: false, limit: 250 }),
  })

  if (customer.isLoading) return <section><h1>Customer</h1><p>Loading…</p></section>
  if (customer.error || !customer.data) return <section><h1>Customer</h1><p className="error">{customer.error instanceof Error ? customer.error.message : 'Customer not found'}</p><Link to="/customers">Back to customers</Link></section>

  const row = customer.data
  const allOrders = [...(orders.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  const activeOrders = allOrders.filter(order => !['Completed', 'Cancelled'].includes(order.status))
  const allIssues = issues.data?.issues ?? []
  const openIssues = allIssues.filter(issue => issue.status !== 'Resolved')
  const allTasks = tasks.data?.tasks ?? []
  const openTasks = allTasks.filter(task => !['Completed', 'Cancelled'].includes(task.status))
  const allMailboxes = mailboxes.data?.mailboxes ?? []
  const activeMailboxes = allMailboxes.filter(mailbox => mailbox.status !== 'Closed')
  const allShipping = shipping.data?.cases ?? []
  const openShipping = allShipping.filter(item => !['Denied', 'Refunded', 'Resolved'].includes(item.status))
  const locationMap = new Map((session?.locations ?? []).map(location => [location.id, location]))
  const address = [row.address1, row.address2, row.city, row.state, row.postal_code].filter(Boolean).join(', ')

  return <section>
    <div className="page-heading">
      <div><h1>{displayName(row)}</h1><p className="muted">Customer 360° profile{!online ? ' · cached data' : ''}</p></div>
      <div className="button-row">
        {online && <Link className="button" to={`/customers/${row.id}/edit`}>Edit Customer</Link>}
        {online && <Link className="button secondary" to={`/orders/new?customer_id=${row.id}`}>New Work Order</Link>}
        {online && <Link className="button secondary" to={`/issues/new?customer_id=${row.id}`}>New Customer Issue</Link>}
        {online && <Link className="button secondary" to={`/tasks?customer_id=${row.id}&new=1`}>New Task</Link>}
        {online && <Link className="button secondary" to={`/mailboxes?customer_id=${row.id}&new=1`}>New Mailbox</Link>}
        {online && <Link className="button secondary" to={`/shipping?customer_id=${row.id}&new=1`}>New Shipping Case</Link>}
        <Link className="button secondary" to="/customers">Back</Link>
      </div>
    </div>

    <div className="panel detail-grid">
      <div><span>Contact</span><strong>{`${row.first_name} ${row.last_name}`.trim() || '—'}</strong></div>
      <div><span>Company</span><strong>{row.company || '—'}</strong></div>
      <div><span>Phone</span><strong>{row.phone || '—'}</strong></div>
      <div><span>Email</span><strong>{row.email || '—'}</strong></div>
      <div className="span-2"><span>Address</span><strong>{address || '—'}</strong></div>
      <div><span>Tax status</span><strong>{row.tax_exempt ? 'Tax exempt' : 'Taxable'}</strong></div>
      <div><span>Last updated</span><strong>{new Date(row.updated_at).toLocaleString()}</strong></div>
      {row.notes && <div className="span-2"><span>Customer notes</span><strong className="prewrap">{row.notes}</strong></div>}
    </div>

    <div className="metric-grid customer-profile-metrics">
      <div className="metric"><span>Active print orders</span><strong>{activeOrders.length}</strong></div>
      <div className="metric"><span>Open customer issues</span><strong>{online ? openIssues.length : '—'}</strong></div>
      <div className="metric"><span>Open tasks</span><strong>{online ? openTasks.length : '—'}</strong></div>
      <div className="metric"><span>Active mailboxes</span><strong>{online ? activeMailboxes.length : '—'}</strong></div>
      <div className="metric"><span>Open shipping cases</span><strong>{online ? openShipping.length : '—'}</strong></div>
      <div className="metric"><span>Print orders on file</span><strong>{allOrders.length}</strong></div>
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Shipping, Claims &amp; GSR</h2><Link to={`/shipping?customer_id=${row.id}`}>View shipping cases</Link></div>
      {!online ? <p className="muted">Shipping cases require an online connection.</p> : shipping.isLoading ? <p>Loading shipping cases…</p> : allShipping.length ? <div className="table-wrap"><table>
        <thead><tr><th>Tracking</th><th>Store</th><th>Type</th><th>Status</th><th>Follow-up</th><th>Reference</th><th>Approved</th></tr></thead>
        <tbody>{allShipping.slice(0,10).map(item => <tr key={item.id}>
          <td><strong>{item.tracking_number}</strong><small className="issue-meta">{item.carrier} {item.service_level}</small></td>
          <td>{item.store?`${item.store.name} #${item.store.store_number}`:'—'}</td><td>{item.case_type}</td><td>{item.status}</td><td>{item.follow_up_date||'—'}</td><td>{item.carrier_reference||'—'}</td><td>${Number(item.amount_approved).toFixed(2)}</td>
        </tr>)}</tbody>
      </table></div> : <p className="empty-state">No shipping cases are linked to this customer.</p>}
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Mailboxes</h2><Link to={`/mailboxes?customer_id=${row.id}`}>View mailboxes</Link></div>
      {!online ? <p className="muted">Mailbox records require an online connection.</p> : mailboxes.isLoading ? <p>Loading mailboxes…</p> : allMailboxes.length ? <div className="table-wrap"><table>
        <thead><tr><th>Mailbox</th><th>Store</th><th>Status</th><th>Renewal</th><th>Compliance</th><th>Balance</th></tr></thead>
        <tbody>{allMailboxes.map(mailbox => <tr key={mailbox.id} className={mailbox.days_overdue>0?'overdue-row':undefined}>
          <td><strong>#{mailbox.mailbox_number}</strong></td><td>{mailbox.store?`${mailbox.store.name} #${mailbox.store.store_number}`:'—'}</td><td>{mailbox.status}</td><td>{mailbox.renewal_date||'No date'}{mailbox.days_overdue>0&&<small className="issue-meta">{mailbox.days_overdue} days overdue</small>}</td><td>{mailbox.compliance_complete?'Complete':mailbox.missing_compliance.join(', ')}</td><td>${Number(mailbox.balance_due).toFixed(2)}</td>
        </tr>)}</tbody>
      </table></div> : <p className="empty-state">No mailboxes are linked to this customer.</p>}
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Print Orders</h2><Link to={`/orders?customer_id=${row.id}`}>View work orders</Link></div>
      {orders.isLoading ? <p>Loading print orders…</p> : allOrders.length ? <div className="table-wrap"><table>
        <thead><tr><th>Order</th><th>Store</th><th>Status</th><th>Priority</th><th>Due</th><th>Description</th><th>Total</th></tr></thead>
        <tbody>{allOrders.slice(0, 10).map(order => {
          const location = locationMap.get(order.location_id)
          return <tr key={order.id}><td><Link to={`/orders/${order.id}`}>{order.order_number}</Link></td><td>{location ? `${location.name} #${location.store_number}` : '—'}</td><td>{order.status}</td><td>{order.priority}</td><td>{order.due_date || '—'}</td><td>{order.description || '—'}</td><td>${Number(order.total).toFixed(2)}</td></tr>
        })}</tbody>
      </table></div> : <p className="empty-state">No print orders are linked to this customer.</p>}
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Customer Issues</h2><Link to={`/issues?customer_id=${row.id}`}>View cases</Link></div>
      {!online ? <p className="muted">Customer issues require an online connection.</p> : issues.isLoading ? <p>Loading customer issues…</p> : allIssues.length ? <div className="table-wrap"><table>
        <thead><tr><th>Case</th><th>Store</th><th>Status</th><th>Priority</th><th>Follow-up</th><th>Next action</th></tr></thead>
        <tbody>{allIssues.slice(0, 10).map(issue => <tr key={issue.id}><td><Link to={`/issues/${issue.id}`}>{issue.title}</Link><small className="issue-meta">{issue.reference}</small></td><td>{issue.store ? `${issue.store.name} #${issue.store.store_number}` : '—'}</td><td>{issue.status}</td><td>{issue.priority}</td><td>{issue.follow_up_date || '—'}</td><td>{issue.next_action || '—'}</td></tr>)}</tbody>
      </table></div> : <p className="empty-state">No customer issues are linked to this customer.</p>}
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Tasks & Follow-Ups</h2><Link to={`/tasks?customer_id=${row.id}`}>View tasks</Link></div>
      {!online ? <p className="muted">Tasks require an online connection.</p> : tasks.isLoading ? <p>Loading tasks…</p> : allTasks.length ? <div className="table-wrap"><table>
        <thead><tr><th>Task</th><th>Store</th><th>Status</th><th>Priority</th><th>Due</th><th>Assigned</th></tr></thead>
        <tbody>{allTasks.slice(0, 10).map(task => <tr key={task.id}><td>{task.title}</td><td>{task.store ? `${task.store.name} #${task.store.store_number}` : '—'}</td><td>{task.status}</td><td>{task.priority}</td><td>{task.due_date || '—'}</td><td>{task.assignee?.name || 'Unassigned'}</td></tr>)}</tbody>
      </table></div> : <p className="empty-state">No tasks are linked to this customer.</p>}
    </div>
  </section>
}
