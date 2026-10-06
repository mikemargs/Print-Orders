import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, apiFetch } from '../../api/http'
import { listIssues } from '../../api/issues'
import { createTask, getTask, taskOptions, taskPriorities, taskStatuses, updateTask, type OperationsTask, type TaskInput } from '../../api/tasks'
import type { Customer, WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

async function allCustomers(){
  const rows:Customer[]=[]
  for(let offset=0;;offset+=200){
    const result=await apiFetch<{customers:Customer[]}>(`/api/customers?limit=200&offset=${offset}`)
    rows.push(...result.customers)
    if(result.customers.length<200)return rows
  }
}
async function matchingOrders(locationId:string,customerId:string|null){
  const rows:WorkOrder[]=[]
  for(let offset=0;;offset+=250){
    const params=new URLSearchParams({limit:'250',offset:String(offset),location_id:locationId})
    if(customerId)params.set('customer_id',customerId)
    const result=await apiFetch<{orders:WorkOrder[]}>(`/api/orders?${params}`)
    rows.push(...result.orders)
    if(result.orders.length<250)return rows
  }
}
function inputFrom(task:OperationsTask):TaskInput{
  return {
    location_id:task.location_id,title:task.title,description:task.description,status:task.status,
    priority:task.priority,assigned_employee_id:task.assigned_employee_id,due_date:task.due_date,
    customer_id:task.customer_id,work_order_id:task.work_order_id,issue_id:task.issue_id,
  }
}

export function TaskEditor(){
  const {id}=useParams();const {online}=useOnline()
  const query=useQuery({queryKey:['tasks','detail',id],queryFn:()=>getTask(id!),enabled:!!id&&online})
  if(id&&!query.data)return <section><h1>Task</h1>{!online?<p className="offline-banner">Tasks require an online connection.</p>:query.error?<p className="error" role="alert">{query.error.message} <button onClick={()=>void query.refetch()}>Retry task</button></p>:<p>Loading task…</p>}<Link to="/tasks">Back to tasks</Link></section>
  return <TaskForm key={id||'new'} source={query.data}/>
}

function TaskForm({source}:{source?:OperationsTask}){
  const {session}=useSession();const {online}=useOnline();const navigate=useNavigate();const queryClient=useQueryClient()
  const [current,setCurrent]=useState(source)
  const [values,setValues]=useState<TaskInput>(()=>source?inputFrom(source):{
    location_id:session?.location.id||'',title:'',description:'',status:'Open',priority:'Normal',
    assigned_employee_id:null,due_date:null,customer_id:null,work_order_id:null,issue_id:null,
  })
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');const [conflict,setConflict]=useState<OperationsTask|null>(null)
  const customers=useQuery({queryKey:['tasks','customers'],queryFn:allCustomers,enabled:online})
  const options=useQuery({queryKey:['tasks','options'],queryFn:taskOptions,enabled:online})
  const orders=useQuery({queryKey:['tasks','orders',values.location_id,values.customer_id],queryFn:()=>matchingOrders(values.location_id,values.customer_id),enabled:online&&!!values.location_id})
  const issues=useQuery({queryKey:['tasks','issues',values.location_id,values.customer_id],queryFn:()=>listIssues({location_id:values.location_id,customer_id:values.customer_id||'',limit:250,offset:0}),enabled:online&&!!values.location_id})
  const canWrite=online&&!!session&&(session.employee.role==='admin'||(current?.location_id||values.location_id)===session.location.id)
  const eligibleEmployees=options.data?.employees.filter(employee=>employee.role==='admin'||!employee.location_ids.length||employee.location_ids.includes(values.location_id))||[]
  function change<K extends keyof TaskInput>(key:K,value:TaskInput[K]){
    setValues(old=>({...old,[key]:value,
      ...(key==='location_id'?{assigned_employee_id:null,work_order_id:null,issue_id:null}:{}),
      ...(key==='customer_id'?{work_order_id:null,issue_id:null}:{})
    }))
  }
  async function save(event:FormEvent){
    event.preventDefault();if(!canWrite||busy)return
    setBusy(true);setError('');setNotice('')
    try{
      const row=current
        ?await updateTask(current.id,{...values,version:current.version})
        :await createTask(values)
      setCurrent(row);setValues(inputFrom(row));setConflict(null);setNotice('Task saved.')
      await queryClient.invalidateQueries({queryKey:['tasks']})
      if(!current)navigate(`/tasks/${row.id}`,{replace:true})
    }catch(e){
      if(e instanceof ApiError&&e.status===409&&e.current){setConflict(e.current as OperationsTask);setError('This task changed on another device. Review the current task before saving again.')}
      else setError(e instanceof Error?e.message:'Unable to save task')
    }finally{setBusy(false)}
  }
  const visibleLocations=session?.locations.filter(location=>session.employee.role==='admin'||location.id===session.location.id||location.id===current?.location_id)||[]
  return <section>
    <div className="page-heading"><div><h1>{current?'Task / Follow-Up':'New Task / Follow-Up'}</h1>{current&&<p className="muted">{current.store?.name} #{current.store?.store_number} · Version {current.version}</p>}</div><Link className="button secondary" to="/tasks">Back to tasks</Link></div>
    {!online&&<p className="offline-banner">Tasks require an online connection.</p>}
    {online&&!canWrite&&<p className="offline-banner">Switch to {current?.store?.name||'the task store'} to update this task. You can still review it here.</p>}
    {error&&<p className="error" role="alert">{error}</p>}{notice&&<p className="issue-success" role="status">{notice}</p>}
    {conflict&&<div className="conflict-banner"><strong>Current task: {conflict.title} · {conflict.status}</strong><p>{conflict.description||'No description'}</p><button type="button" onClick={()=>{setCurrent(conflict);setValues(inputFrom(conflict));setConflict(null);setError('')}}>Load current task</button></div>}
    <form className="panel" onSubmit={save}><fieldset className="form-grid task-fieldset" disabled={!canWrite||busy||!!conflict}>
      <label>Store<select required value={values.location_id} onChange={e=>change('location_id',e.target.value)}>{visibleLocations.map(location=><option key={location.id} value={location.id}>{location.name} #{location.store_number}</option>)}</select></label>
      <label>Assigned employee<select value={values.assigned_employee_id||''} onChange={e=>change('assigned_employee_id',e.target.value||null)}><option value="">Unassigned</option>{eligibleEmployees.map(employee=><option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></label>
      <label className="span-2">Task title<input required maxLength={200} value={values.title} onChange={e=>change('title',e.target.value)}/></label>
      <label className="span-2">Description<textarea rows={4} maxLength={10000} value={values.description} onChange={e=>change('description',e.target.value)}/></label>
      <label>Status<select value={values.status} onChange={e=>change('status',e.target.value)}>{taskStatuses.map(status=><option key={status}>{status}</option>)}</select></label>
      <label>Priority<select value={values.priority} onChange={e=>change('priority',e.target.value)}>{taskPriorities.map(priority=><option key={priority}>{priority}</option>)}</select></label>
      <label>Due date<input type="date" value={values.due_date||''} onChange={e=>change('due_date',e.target.value||null)}/></label>
      <label>Related customer<select value={values.customer_id||''} onChange={e=>change('customer_id',e.target.value||null)}><option value="">No customer</option>{customers.data?.map(customer=><option key={customer.id} value={customer.id}>{customer.company||`${customer.first_name} ${customer.last_name}`.trim()||'Unnamed customer'}</option>)}</select></label>
      <label>Linked print order<select value={values.work_order_id||''} onChange={e=>change('work_order_id',e.target.value||null)}><option value="">No print order</option>{orders.data?.map(order=><option key={order.id} value={order.id}>{order.order_number} · {order.description||'No description'}</option>)}{current?.order&&!orders.data?.some(order=>order.id===current.work_order_id)&&<option value={current.order.id}>{current.order.order_number}</option>}</select></label>
      <label>Linked customer issue<select value={values.issue_id||''} onChange={e=>change('issue_id',e.target.value||null)}><option value="">No customer issue</option>{issues.data?.issues.map(issue=><option key={issue.id} value={issue.id}>{issue.reference} · {issue.title}</option>)}{current?.issue&&!issues.data?.issues.some(issue=>issue.id===current.issue_id)&&<option value={current.issue.id}>{current.issue.reference} · {current.issue.title}</option>}</select></label>
      {current&&<div className="span-2 button-row">{current.customer_id&&<Link to={`/customers/${current.customer_id}`}>Open customer</Link>}{current.work_order_id&&<Link to={`/orders/${current.work_order_id}`}>Open print order</Link>}{current.issue_id&&<Link to={`/issues/${current.issue_id}`}>Open customer issue</Link>}</div>}
      <div className="form-actions span-2"><button disabled={!canWrite||busy||!!conflict}>{busy?'Saving…':'Save task'}</button></div>
    </fieldset>
    {customers.error&&<p className="error">Customer choices: {customers.error.message}</p>}
    {options.error&&<p className="error">Employee choices: {options.error.message}</p>}
    {orders.error&&<p className="error">Order choices: {orders.error.message}</p>}
    {issues.error&&<p className="error">Issue choices: {issues.error.message}</p>}
    </form>
  </section>
}
