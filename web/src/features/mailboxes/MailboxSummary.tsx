import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getMailboxSummary } from '../../api/mailboxes'
import { useOnline } from '../../offline/OnlineState'

export function MailboxSummary(){
  const {online}=useOnline()
  const query=useQuery({queryKey:['mailbox-summary'],queryFn:getMailboxSummary,enabled:online,refetchInterval:30000})
  return <div className="panel issue-summary">
    <div className="section-heading"><h2>Mailbox Management</h2><Link to="/mailboxes">View mailboxes</Link></div>
    {!online?<p className="muted">Mailbox summaries require an online connection.</p>:query.isLoading?<p>Loading mailbox summary…</p>:query.error?<p className="error">Unable to load mailbox summary.</p>:query.data&&<div className="metric-grid">
      <div className="metric"><span>Active</span><strong>{query.data.active}</strong></div>
      <div className="metric"><span>Overdue</span><strong>{query.data.overdue}</strong></div>
      <div className="metric"><span>Due in 30 days</span><strong>{query.data.due_30}</strong></div>
      <div className="metric"><span>Missing compliance</span><strong>{query.data.missing_compliance}</strong></div>
    </div>}
  </div>
}
