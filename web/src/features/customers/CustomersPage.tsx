import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { Customer } from '../../api/types'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cachedCustomers } from '../../offline/db'

export function CustomersPage() {
  const [search, setSearch] = useState(''); const {online}=useOnline()
  const query = useQuery({ queryKey:['customers',search,online], queryFn:async()=>{if(!online){const needle=search.toLowerCase();return {customers:(await cachedCustomers()).filter(c=>`${c.company} ${c.first_name} ${c.last_name} ${c.phone} ${c.email}`.toLowerCase().includes(needle))}}const result=await apiFetch<{customers:Customer[]}>(`/api/customers?search=${encodeURIComponent(search)}&limit=200`);await cacheCustomers(result.customers);return result} })
  return <section><div className="page-heading"><div><h1>Customers</h1>{!online&&<p className="muted">Showing cached customers · read only</p>}</div>{online&&<Link className="button" to="/customers/new">New customer</Link>}</div>
    <div className="toolbar"><input placeholder="Search customers…" value={search} onChange={e => setSearch(e.target.value)} /></div>
    <div className="panel table-wrap"><table><thead><tr><th>Company / Name</th><th>Phone</th><th>Email</th><th>Location</th></tr></thead><tbody>{query.data?.customers.map(c => <tr key={c.id}><td><Link to={`/customers/${c.id}`}>{c.company || `${c.first_name} ${c.last_name}`.trim() || 'Unnamed customer'}</Link></td><td>{c.phone}</td><td>{c.email}</td><td>{[c.city,c.state].filter(Boolean).join(', ')}</td></tr>)}</tbody></table>{!query.isLoading && !query.data?.customers.length && <p className="empty-state">No customers found.</p>}</div>
  </section>
}
