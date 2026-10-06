import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listTasks, taskOptions, taskPriorities, taskStatuses } from '../../api/tasks'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

const closed=new Set(['Completed','Cancelled'])

export function TasksPage(){
  const {session}=useSession();const {online}=useOnline();const [offset,setOffset]=useState(0)
  const [filters,setFilters]=useState({search:'',location_id:'',status:'',priority:'',assigned_employee_id:'',open_only:true})
  function change(key:string,value:string|boolean){setFilters(old=>({...old,[key]:value}));setOffset(0)}
  const query=useQuery({
    queryKey:['tasks','list',filters,offset],
    queryFn:()=>listTasks({...filters,limit:50,offset}),
    enabled:online,
    refetchOnWindowFocus:true,
  })
  const options=useQuery({queryKey:['tasks','options'],queryFn:taskOptions,enabled:online})
  const today=new Date().toISOString().slice(0,10)
  const overdue=(task:{due_date:string|null;status:string})=>!!task.due_date&&task.due_date<today&&!closed.has(task.status)
  return <section>
    <div className="page-heading"><div><h1>Tasks &amp; Follow-Ups</h1><p className="muted">Shared operational work across every store.</p></div>{online&&<Link className="button" to="/tasks/new">New task</Link>}</div>
    {!online&&<p className="offline-banner">Tasks &amp; Follow-Ups require an online connection.</p>}
    <div className="task-filters">
      <label>Search<input value={filters.search} onChange={e=>change('search',e.target.value)} placeholder="Task title or description"/></label>
      <label>Store<select value={filters.location_id} onChange={e=>change('location_id',e.target.value)}><option value="">All stores</option>{session?.locations.map(l=><option key={l.id} value={l.id}>{l.name} #{l.store_number}</option>)}</select></label>
      <label>Status<select value={filters.status} onChange={e=>{setFilters(old=>({...old,status:e.target.value,open_only:!e.target.value}));setOffset(0)}}><option value="">All open</option>{taskStatuses.map(s=><option key={s}>{s}</option>)}</select></label>
      <label>Priority<select value={filters.priority} onChange={e=>change('priority',e.target.value)}><option value="">Any priority</option>{taskPriorities.map(p=><option key={p}>{p}</option>)}</select></label>
      <label>Assigned<select value={filters.assigned_employee_id} onChange={e=>change('assigned_employee_id',e.target.value)}><option value="">Anyone</option>{options.data?.employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
      <label className="checkbox"><input type="checkbox" checked={!filters.open_only&&!filters.status} onChange={e=>{setFilters(old=>({...old,status:'',open_only:!e.target.checked}));setOffset(0)}}/>Include completed / cancelled</label>
    </div>
    <div className="panel">
      {query.isLoading?<p>Loading tasks…</p>:query.error?<p className="error" role="alert">{query.error.message} <button onClick={()=>void query.refetch()}>Retry tasks</button></p>:query.data?<>
        <div className="section-heading"><h2>Operational tasks</h2><span>{query.data.total} matching tasks</span></div>
        {query.data.tasks.length?<div className="table-wrap"><table><thead><tr><th>Task</th><th>Store</th><th>Status</th><th>Priority</th><th>Assigned</th><th>Due</th><th>Related</th></tr></thead><tbody>{query.data.tasks.map(task=><tr key={task.id} className={overdue(task)?'overdue-row':undefined}>
          <td><Link to={`/tasks/${task.id}`}>{task.title}</Link><small className="task-meta">{task.description||'No description'}</small></td>
          <td>{task.store?`${task.store.name} #${task.store.store_number}`:'—'}</td>
          <td>{task.status}</td><td><span className={`task-priority ${task.priority.toLowerCase()}`}>{task.priority}</span></td>
          <td>{task.assignee?.name||'Unassigned'}</td><td>{task.due_date||'No date'}{overdue(task)&&<strong className="task-meta">Overdue</strong>}</td>
          <td>{task.customer&&(task.customer.company||`${task.customer.first_name} ${task.customer.last_name}`.trim())}{task.order&&<small className="task-meta">{task.order.order_number}</small>}{task.issue&&<small className="task-meta">{task.issue.reference}</small>}{!task.customer&&!task.order&&!task.issue&&'—'}</td>
        </tr>)}</tbody></table></div>:<p className="empty-state">No tasks match these filters.</p>}
        <div className="button-row issue-pagination"><button className="secondary" disabled={offset===0||!online} onClick={()=>setOffset(x=>Math.max(0,x-50))}>Previous page</button><span>Page {Math.floor(offset/50)+1}</span><button className="secondary" disabled={offset+50>=query.data.total||!online} onClick={()=>setOffset(x=>x+50)}>Next page</button></div>
      </>:null}
    </div>
  </section>
}
