import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { TaskSummary } from '../../api/types'
import { useOnline } from '../../offline/OnlineState'

export function TaskSummaryPanel() {
  const { online } = useOnline()
  const summary = useQuery({
    queryKey: ['tasks', 'summary'],
    queryFn: () => apiFetch<TaskSummary>('/api/tasks/summary'),
    enabled: online,
    refetchInterval: 30_000,
  })
  if (!online) return null
  const data = summary.data
  return <div className="panel">
    <div className="section-heading"><h2>Tasks &amp; Follow-Ups</h2><Link to="/tasks">View tasks</Link></div>
    {summary.isLoading ? <p>Loading…</p> : <div className="metric-grid">
      <div className="metric"><span>Open</span><strong>{data?.open ?? 0}</strong></div>
      <div className="metric"><span>Due today</span><strong>{data?.due_today ?? 0}</strong></div>
      <div className="metric"><span>Overdue</span><strong>{data?.overdue ?? 0}</strong></div>
      <div className="metric"><span>Assigned to me</span><strong>{data?.assigned_to_me ?? 0}</strong></div>
    </div>}
  </div>
}
