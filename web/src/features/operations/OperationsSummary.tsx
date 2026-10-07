import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getOperationsSummary } from '../../api/operations'
import { useOnline } from '../../offline/OnlineState'

export function OperationsSummary(){
  const {online}=useOnline()
  const query=useQuery({queryKey:['operations-summary'],queryFn:getOperationsSummary,enabled:online,refetchInterval:30000})
  return <div className="panel issue-summary">
    <div className="section-heading"><h2>Store Operations</h2><Link to="/operations">View checklists</Link></div>
    {!online?<p className="muted">Operations checklist status requires an online connection.</p>:query.isLoading?<p>Loading operations status…</p>:query.error?<p className="error">Unable to load operations status.</p>:query.data&&<>
      <div className="metric-grid">
        <div className="metric"><span>Expected today</span><strong>{query.data.expected}</strong></div>
        <div className="metric"><span>Completed</span><strong>{query.data.completed}</strong></div>
        <div className="metric"><span>Pending</span><strong>{query.data.pending}</strong></div>
        <div className="metric"><span>Required pending</span><strong>{query.data.required_pending}</strong></div>
      </div>
      <div className="store-summary-grid">{query.data.stores.map(store=><div className="store-summary-card" key={store.location_id}><span>{store.store}</span><strong>{store.completed}/{store.expected}</strong><small>{store.required_pending?store.required_pending+' required pending':'Required items complete'}</small></div>)}</div>
    </>}
  </div>
}
