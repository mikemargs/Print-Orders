import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api/http'
import type { Employee, StoreTask } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

const statuses = ['Open', 'In Progress', 'Waiting', 'Completed', 'Cancelled']
const priorities = ['Low', 'Normal', 'High', 'Urgent']

export function TasksPage() {
  const { session } = useSession()
  const { online } = useOnline()
  const queryClient = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [error, setError] = useState('')
  const [locationFilter, setLocationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('active')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('Normal')
  const [dueDate, setDueDate] = useState('')
  const [assignee, setAssignee] = useState('')

  const tasks = useQuery({
    queryKey: ['tasks', locationFilter, statusFilter],
    queryFn: () => apiFetch<{ tasks: StoreTask[]; total: number }>(
      `/api/tasks?limit=250${locationFilter ? '&location_id=' + encodeURIComponent(locationFilter) : ''}${statusFilter === 'active' ? '&open_only=true' : statusFilter ? '&status=' + encodeURIComponent(statusFilter) : ''}`,
    ),
    enabled: online,
  })
  const options = useQuery({
    queryKey: ['task-options'],
    queryFn: () => apiFetch<{ employees: Employee[] }>('/api/tasks/options'),
    enabled: online,
  })
  const eligibleEmployees = useMemo(() => (options.data?.employees ?? []).filter(employee =>
    employee.role === 'admin' || !employee.location_ids.length || employee.location_ids.includes(session?.location.id ?? ''),
  ), [options.data?.employees, session?.location.id])

  useEffect(() => {
    if (assignee && !eligibleEmployees.some(employee => employee.id === assignee)) setAssignee('')
  }, [assignee, eligibleEmployees])

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!session || !title.trim()) return
    setError('')
    try {
      await apiFetch('/api/tasks', {
        method: 'POST',
        body: JSON.stringify({
          location_id: session.location.id,
          title: title.trim(),
          description: description.trim(),
          priority,
          due_date: dueDate || null,
          assigned_employee_id: assignee || null,
        }),
      })
      setTitle(''); setDescription(''); setPriority('Normal'); setDueDate(''); setAssignee(''); setShowNew(false)
      await queryClient.invalidateQueries({ queryKey: ['tasks'] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create task')
    }
  }

  async function setStatus(task: StoreTask, status: string) {
    setError('')
    try {
      await apiFetch(`/api/tasks/${task.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ version: task.version, status }),
      })
      await queryClient.invalidateQueries({ queryKey: ['tasks'] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update task')
    }
  }

  if (!online) return <section><div className="page-heading"><h1>Tasks &amp; Follow-Ups</h1></div><div className="panel muted">Tasks require an internet connection in this first Operations Hub version.</div></section>

  const today = new Date().toISOString().slice(0, 10)
  return <section>
    <div className="page-heading">
      <div><h1>Tasks &amp; Follow-Ups</h1><p className="muted">Company-wide operational tasks, assignments and follow-ups.</p></div>
      <button onClick={() => setShowNew(value => !value)}>{showNew ? 'Close' : 'New Task'}</button>
    </div>
    {showNew && <form className="panel form-stack" onSubmit={create}>
      <div className="section-heading"><h2>New task · {session?.location.name} #{session?.location.store_number}</h2></div>
      <div className="form-grid">
        <label className="span-2">Task title<input value={title} onChange={event => setTitle(event.target.value)} required maxLength={200}/></label>
        <label>Priority<select value={priority} onChange={event => setPriority(event.target.value)}>{priorities.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Due date<input type="date" value={dueDate} onChange={event => setDueDate(event.target.value)}/></label>
        <label>Assign to<select value={assignee} onChange={event => setAssignee(event.target.value)}><option value="">Unassigned</option>{eligibleEmployees.map(employee => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></label>
        <label className="span-2">Details<textarea rows={3} value={description} onChange={event => setDescription(event.target.value)}/></label>
      </div>
      <div className="form-actions"><button type="submit">Create Task</button></div>
    </form>}
    {error && <p className="error">{error}</p>}
    <div className="panel filters">
      <label>Store<select value={locationFilter} onChange={event => setLocationFilter(event.target.value)}><option value="">All stores</option>{session?.locations.map(location => <option key={location.id} value={location.id}>{location.name} #{location.store_number}</option>)}</select></label>
      <label>Status<select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="active">Active</option><option value="">All</option>{statuses.map(value => <option key={value}>{value}</option>)}</select></label>
    </div>
    <div className="panel table-wrap">
      <table><thead><tr><th>Store</th><th>Task</th><th>Status</th><th>Priority</th><th>Due</th><th>Assigned</th><th>Action</th></tr></thead>
      <tbody>{(tasks.data?.tasks ?? []).map(task => {
        const overdue = task.due_date && task.due_date < today && !['Completed','Cancelled'].includes(task.status)
        return <tr key={task.id} className={overdue ? 'overdue-row' : undefined}>
          <td>{task.store ? `${task.store.name} #${task.store.store_number}` : '—'}</td>
          <td><strong>{task.title}</strong>{task.description && <><br/><small className="muted">{task.description}</small></>}</td>
          <td>{task.status}</td><td><span className={`priority ${task.priority.toLowerCase()}`}>{task.priority}</span></td>
          <td>{task.due_date || '—'}</td><td>{task.assignee?.name || 'Unassigned'}</td>
          <td>{task.status === 'Completed' ? <button className="secondary" onClick={() => void setStatus(task, 'Open')}>Reopen</button> : <button onClick={() => void setStatus(task, 'Completed')}>Complete</button>}</td>
        </tr>
      })}</tbody></table>
      {!tasks.isLoading && !(tasks.data?.tasks.length) && <p className="empty-state">No tasks match these filters.</p>}
    </div>
  </section>
}
