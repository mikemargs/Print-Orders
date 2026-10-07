import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getShippingSummary } from '../../api/shipping'
import { useOnline } from '../../offline/OnlineState'

export function ShippingSummary(){
  const {online}=useOnline()
  const query=useQuery({queryKey:['shipping-summary'],queryFn:getShippingSummary,enabled:online,refetchInterval:30000})
  return <div className="panel issue-summary">
    <div className="section-heading"><h2>Shipping, Claims & GSR</h2><Link to="/shipping">View cases</Link></div>
    {!online?<p className="muted">Shipping case summaries require an online connection.</p>:query.isLoading?<p>Loading shipping summary…</p>:query.error?<p className="error">Unable to load shipping summary.</p>:query.data&&<div className="metric-grid">
      <div className="metric"><span>Open cases</span><strong>{query.data.open}</strong></div>
      <div className="metric"><span>Overdue follow-ups</span><strong>{query.data.overdue_followups}</strong></div>
      <div className="metric"><span>GSR pending</span><strong>{query.data.gsr_pending}</strong></div>
      <div className="metric"><span>Claims pending</span><strong>{query.data.claims_pending}</strong></div>
    </div>}
  </div>
}
