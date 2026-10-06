import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getTaskSummary } from '../../api/tasks'
import { useOnline } from '../../offline/OnlineState'

export function TaskSummary(){
  const {online}=useOnline()
  const query=useQuery({
    queryKey:['tasks','summary'],
    queryFn:()=>getTaskSummary({open_only:true}),
    enabled:online,
    refetchOnWindowFocus:true,
  })
  if(!online)return <div className="panel"><div className="section-heading"><h2>Tasks &amp; Follow-Ups</h2><Link to="/tasks">View tasks</Link></div><p className="muted">Task summaries require an online connection.</p></div>
  return <div className="panel task-summary">
    <div className="section-heading"><h2>Tasks &amp; Follow-Ups</h2><Link to="/tasks">View tasks</Link></div>
    {query.isLoading?<p>Loading task summary…</p>:query.error?<p className="error" role="alert">{query.error.message} <button onClick={()=>void query.refetch()}>Retry summary</button></p>:query.data&&<div className="metric-grid">
      <div className="metric"><span>Open tasks</span><strong>{query.data.open}</strong></div>
      <div className="metric"><span>Overdue</span><strong>{query.data.overdue}</strong></div>
      <div className="metric"><span>Due today</span><strong>{query.data.due_today}</strong></div>
      <div className="metric"><span>Assigned to me</span><strong>{query.data.assigned_to_me}</strong></div>
    </div>}
  </div>
}
