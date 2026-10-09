import { SummaryCard } from '../../components/SummaryCard'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getTaskSummary } from '../../api/tasks'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

export function TaskSummary(){
  const {online}=useOnline()
  const {session}=useSession()
  const query=useQuery({queryKey:['task-summary',session?.company.id,session?.employee.id],queryFn:getTaskSummary,enabled:online,refetchInterval:30000})
  return <div className="panel issue-summary">
    <div className="section-heading"><h2>Tasks & Follow-Ups</h2><Link to="/tasks">View tasks</Link></div>
    {!online?<p className="muted">Task summaries require an online connection.</p>:query.isLoading?<p>Loading task summary…</p>:query.error?<p className="error">Unable to load task summary.</p>:query.data&&<div className="metric-grid">
      <SummaryCard to="/tasks?view=open"><span>Open tasks</span><strong>{query.data.open}</strong></SummaryCard>
      <SummaryCard to="/tasks?view=overdue"><span>Overdue</span><strong>{query.data.overdue}</strong></SummaryCard>
      <SummaryCard to="/tasks?view=high_priority"><span>High / urgent</span><strong>{query.data.high_priority}</strong></SummaryCard>
      <SummaryCard to="/tasks?view=mine"><span>Assigned to me</span><strong>{query.data.assigned_to_me}</strong></SummaryCard>
    </div>}
  </div>
}
