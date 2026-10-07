import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api/http'
import { getTaskOptions, listTasks } from '../../api/tasks'
import type { OperationalTask } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

const statuses = ['Open','In Progress','Waiting','Completed','Cancelled'] as const
const priorities = ['Low','Normal','High','Urgent'] as const

export function TasksPage(){
  const {session}=useSession()
  const {online}=useOnline()
  const qc=useQueryClient()
  const [showCreate,setShowCreate]=useState(false)
  const [search,setSearch]=useState('')
  const [status,setStatus]=useState('')
  const [locationId,setLocationId]=useState('')
  const [assignedEmployeeId,setAssignedEmployeeId]=useState('')
  const [includeClosed,setIncludeClosed]=useState(false)
  const [form,setForm]=useState({
    location_id:session?.location.id||'',
    title:'',
    description:'',
    status:'Open',
    priority:'Normal',
    due_date:'',
    assigned_employee_id:'',
    customer_id:'',
    work_order_id:'',
    customer_issue_id:'',
  })

  const query=useQuery({
    queryKey:['tasks',search,status,locationId,assignedEmployeeId,includeClosed],
    queryFn:()=>listTasks({
      search,
      status,
      location_id:locationId,
      assigned_employee_id:assignedEmployeeId,
      open_only:!includeClosed&&!status,
      limit:250,
    }),
    enabled:online,
  })
  const options=useQuery({queryKey:['task-options'],queryFn:getTaskOptions,enabled:online})

  const create=useMutation({
    mutationFn:()=>apiFetch<OperationalTask>('/api/tasks',{
      method:'POST',
      body:JSON.stringify({
        ...form,
        due_date:form.due_date||null,
        assigned_employee_id:form.assigned_employee_id||null,
        customer_id:form.customer_id||null,
        work_order_id:form.work_order_id||null,
        customer_issue_id:form.customer_issue_id||null,
      }),
    }),
    onSuccess:async()=>{
      setShowCreate(false)
      setForm(old=>({...old,title:'',description:'',due_date:'',assigned_employee_id:'',customer_id:'',work_order_id:'',customer_issue_id:''}))
      await qc.invalidateQueries({queryKey:['tasks']})
      await qc.invalidateQueries({queryKey:['task-summary']})
    },
  })

  const update=useMutation({
    mutationFn:({task,nextStatus}:{task:OperationalTask;nextStatus:string})=>apiFetch<OperationalTask>(`/api/tasks/${task.id}`,{
      method:'PATCH',
      body:JSON.stringify({
        version:task.version,
        location_id:task.location_id,
        title:task.title,
        description:task.description,
        status:nextStatus,
        priority:task.priority,
        due_date:task.due_date,
        assigned_employee_id:task.assigned_employee_id,
        customer_id:task.customer_id,
        work_order_id:task.work_order_id,
        customer_issue_id:task.customer_issue_id,
      }),
    }),
    onSuccess:async()=>{
      await qc.invalidateQueries({queryKey:['tasks']})
      await qc.invalidateQueries({queryKey:['task-summary']})
    },
  })

  const employees=options.data?.employees??[]
  const eligibleEmployees=useMemo(
    ()=>employees.filter(e=>e.role==='admin'||!e.location_ids.length||e.location_ids.includes(form.location_id)),
    [employees,form.location_id],
  )
  const today=new Date().toISOString().slice(0,10)

  return <section>
    <div className="page-heading">
      <div><h1>Tasks & Follow-Ups</h1><p className="muted">Operational work, reminders, and ownership across every store.</p></div>
      {online&&<button onClick={()=>setShowCreate(x=>!x)}>{showCreate?'Close':'New Task'}</button>}
    </div>

    {!online&&<div className="offline-banner">Tasks require an online connection.</div>}

    {showCreate&&<form className="panel form-grid" onSubmit={e=>{e.preventDefault();create.mutate()}}>
      <label>Store<select value={form.location_id} onChange={e=>setForm(old=>({...old,location_id:e.target.value,assigned_employee_id:''}))}>{session?.locations.map(l=><option key={l.id} value={l.id}>{l.name} #{l.store_number}</option>)}</select></label>
      <label>Priority<select value={form.priority} onChange={e=>setForm(old=>({...old,priority:e.target.value}))}>{priorities.map(x=><option key={x}>{x}</option>)}</select></label>
      <label>Due date<input type="date" value={form.due_date} onChange={e=>setForm(old=>({...old,due_date:e.target.value}))}/></label>
      <label>Assign to<select value={form.assigned_employee_id} onChange={e=>setForm(old=>({...old,assigned_employee_id:e.target.value}))}><option value="">Unassigned</option>{eligibleEmployees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
      <label className="span-2">Task title<input required maxLength={220} value={form.title} onChange={e=>setForm(old=>({...old,title:e.target.value}))}/></label>
      <label className="span-2">Description<textarea rows={3} value={form.description} onChange={e=>setForm(old=>({...old,description:e.target.value}))}/></label>
      <label>Customer (optional)<select value={form.customer_id} onChange={e=>setForm(old=>({...old,customer_id:e.target.value}))}><option value="">None</option>{options.data?.customers.map(c=><option key={c.id} value={c.id}>{c.company||`${c.first_name} ${c.last_name}`}</option>)}</select></label>
      <div className="form-actions span-2"><button disabled={create.isPending}>{create.isPending?'Creating…':'Create Task'}</button></div>
      {create.error&&<p className="error span-2">{create.error instanceof Error?create.error.message:'Unable to create task'}</p>}
    </form>}

    <div className="toolbar order-filters">
      <input placeholder="Search tasks…" value={search} onChange={e=>setSearch(e.target.value)}/>
      <select aria-label="Task store filter" value={locationId} onChange={e=>setLocationId(e.target.value)}><option value="">All stores</option>{session?.locations.map(l=><option key={l.id} value={l.id}>{l.name} #{l.store_number}</option>)}</select>
      <select aria-label="Task status filter" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All open</option>{statuses.map(x=><option key={x}>{x}</option>)}</select>
      <select aria-label="Task assignee filter" value={assignedEmployeeId} onChange={e=>setAssignedEmployeeId(e.target.value)}><option value="">Any assignee</option>{employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select>
      <label className="checkbox"><input type="checkbox" checked={includeClosed} onChange={e=>setIncludeClosed(e.target.checked)}/>Include completed/cancelled</label>
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Tasks</h2><span>{query.data?.total??0} matching</span></div>
      {query.isLoading?<p>Loading tasks…</p>:query.error?<p className="error">{query.error instanceof Error?query.error.message:'Unable to load tasks'}</p>:query.data?.tasks.length?<div className="table-wrap"><table>
        <thead><tr><th>Task</th><th>Store</th><th>Priority</th><th>Due</th><th>Assigned</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{query.data.tasks.map(task=><tr key={task.id} className={task.due_date&&task.due_date<today&&!['Completed','Cancelled'].includes(task.status)?'overdue-row':undefined}>
          <td><strong>{task.title}</strong>{task.description&&<small className="issue-meta">{task.description}</small>}{task.customer&&<small className="issue-meta">Customer: {task.customer.company||`${task.customer.first_name} ${task.customer.last_name}`}</small>}</td>
          <td>{task.store?.name} #{task.store?.store_number}</td>
          <td><span className={`issue-priority ${task.priority.toLowerCase()}`}>{task.priority}</span></td>
          <td>{task.due_date||'No date'}{task.due_date&&task.due_date<today&&!['Completed','Cancelled'].includes(task.status)&&<small className="issue-meta">Overdue</small>}</td>
          <td>{task.assignee?.name||'Unassigned'}</td><td>{task.status}</td>
          <td><div className="button-row">{task.status!=='Completed'&&<button className="small-button" onClick={()=>update.mutate({task,nextStatus:'Completed'})}>Complete</button>}{task.status==='Open'&&<button className="small-button secondary" onClick={()=>update.mutate({task,nextStatus:'In Progress'})}>Start</button>}</div></td>
        </tr>)}</tbody>
      </table></div>:<p className="empty-state">No tasks match these filters.</p>}
    </div>
  </section>
}
