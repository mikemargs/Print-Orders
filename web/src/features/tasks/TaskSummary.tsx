import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getTaskSummary } from '../../api/tasks'
import { useOnline } from '../../offline/OnlineState'

export function TaskSummary(){
  const {online}=useOnline()
  const query=useQuery({queryKey:['task-summary'],queryFn:getTaskSummary,enabled:online,refetchInterval:30000})
  return <div className="panel issue-summary">
    <div className="section-heading"><h2>Tasks & Follow-Ups</h2><Link to="/tasks">View tasks</Link></div>
    {!online?<p className="muted">Task summaries require an online connection.</p>:query.isLoading?<p>Loading task summary…</p>:query.error?<p className="error">Unable to load task summary.</p>:query.data&&<div className="metric-grid">
      <div className="metric"><span>Open tasks</span><strong>{query.data.open}</strong></div>
      <div className="metric"><span>Overdue</span><strong>{query.data.overdue}</strong></div>
      <div className="metric"><span>High / urgent</span><strong>{query.data.high_priority}</strong></div>
      <div className="metric"><span>Assigned to me</span><strong>{query.data.assigned_to_me}</strong></div>
    </div>}
  </div>
}
