import { SummaryCard, ViewNotice, useUrlValue, useListView } from '../../components/SummaryCard'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  completeOperationsItem,
  createOperationsTemplate,
  getOperationsChecklist,
  listOperationsTemplates,
  resetOperationsItem,
  updateOperationsTemplate,
  type ChecklistTemplateInput,
} from '../../api/operations'
import type { OperationsChecklistItem } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

const categories: OperationsChecklistItem['category'][] = ['Opening','Closing','Daily','Cleaning','Equipment','Deposit','Supplies','Safety','Other']
const weekdays = [
  {value:0,label:'Mon'},{value:1,label:'Tue'},{value:2,label:'Wed'},{value:3,label:'Thu'},
  {value:4,label:'Fri'},{value:5,label:'Sat'},{value:6,label:'Sun'},
]

function templateValues(item: OperationsChecklistItem): ChecklistTemplateInput {
  return {
    location_id:item.location_id,
    title:item.title,
    description:item.description,
    category:item.category,
    active_days:item.active_days,
    required:item.required,
    active:item.active,
    sort_order:item.sort_order,
  }
}

export function OperationsPage(){
  const {session}=useSession()
  const {online}=useOnline()
  const {view}=useListView()
  const qc=useQueryClient()
  const canManage=session?.employee.role==='supervisor'||session?.employee.role==='admin'
  const [locationId,setLocationId]=useUrlValue('location_id',session?.location.id||'')
  const [date,setDate]=useUrlValue('date','')
  const [showManage,setShowManage]=useState(false)
  const [showInactive,setShowInactive]=useState(false)
  const [form,setForm]=useState<ChecklistTemplateInput>({
    location_id:session?.location.id??'',
    title:'',
    description:'',
    category:'Daily',
    active_days:[0,1,2,3,4,5,6],
    required:true,
    active:true,
    sort_order:0,
  })

  const checklist=useQuery({
    queryKey:['operations-checklist',session?.company.id,locationId,date],
    queryFn:()=>getOperationsChecklist(locationId,date),
    enabled:online&&Boolean(locationId),
  })
  const templates=useQuery({
    queryKey:['operations-templates',locationId,showInactive],
    queryFn:()=>listOperationsTemplates(locationId,showInactive),
    enabled:online&&showManage&&Boolean(locationId)&&locationId!=='all',
  })

  async function refresh(){
    await Promise.all([
      qc.invalidateQueries({queryKey:['operations-checklist']}),
      qc.invalidateQueries({queryKey:['operations-summary']}),
      qc.invalidateQueries({queryKey:['operations-templates']}),
    ])
  }

  const mark=useMutation({
    mutationFn:({item,status}:{item:OperationsChecklistItem;status:'Completed'|'Skipped'})=>completeOperationsItem(item,item.checklist_date??checklist.data?.date??date,status),
    onSuccess:refresh,
  })
  const reset=useMutation({
    mutationFn:(item:OperationsChecklistItem)=>resetOperationsItem(item,item.checklist_date??checklist.data?.date??date),
    onSuccess:refresh,
  })
  const create=useMutation({
    mutationFn:()=>createOperationsTemplate({...form,location_id:locationId}),
    onSuccess:async()=>{
      setForm(old=>({...old,title:'',description:'',sort_order:0}))
      await refresh()
    },
  })
  const toggle=useMutation({
    mutationFn:(item:OperationsChecklistItem)=>updateOperationsTemplate(item,{...templateValues(item),active:!item.active}),
    onSuccess:refresh,
  })

  const grouped=useMemo(()=>{
    const map=new Map<string,OperationsChecklistItem[]>()
    for(const item of checklist.data?.items??[]){
      if(view==='completed'&&item.completion?.status!=='Completed')continue
      if(view==='pending'&&item.completion)continue
      if(view==='required_pending'&&(!item.required||item.completion))continue
      const rows=map.get(item.category)??[]
      rows.push(item)
      map.set(item.category,rows)
    }
    return [...map.entries()]
  },[checklist.data?.items,view])

  const counts=useMemo(()=>{
    const items=checklist.data?.items??[]
    return {
      expected:items.length,
      completed:items.filter(x=>x.completion?.status==='Completed').length,
      skipped:items.filter(x=>x.completion?.status==='Skipped').length,
      pending:items.filter(x=>!x.completion).length,
      requiredPending:items.filter(x=>x.required&&!x.completion).length,
    }
  },[checklist.data?.items])

  function toggleDay(day:number){
    setForm(old=>({
      ...old,
      active_days:old.active_days.includes(day)
        ? old.active_days.filter(x=>x!==day)
        : [...old.active_days,day].sort(),
    }))
  }

  return <section><ViewNotice/>
    <div className="page-heading">
      <div><h1>Store Operations</h1><p className="muted">Daily opening, closing, cleaning, equipment, deposit, supply, and safety checklists.</p></div>
      {canManage&&online&&locationId!=='all'&&<button className="secondary" onClick={()=>setShowManage(x=>!x)}>{showManage?'Close Checklist Setup':'Manage Checklist'}</button>}
    </div>

    {!online&&<div className="offline-banner">Store Operations checklists require an online connection.</div>}

    <div className="toolbar order-filters">
      <label className="compact-filter">Store<select value={locationId} onChange={e=>{setLocationId(e.target.value);setForm(old=>({...old,location_id:e.target.value}))}}><option value="all">All stores</option>{session?.locations.map(l=><option key={l.id} value={l.id}>{l.name} #{l.store_number}</option>)}</select></label>
      <label className="compact-filter">Checklist date (blank for today)<input type="date" value={date} onChange={e=>setDate(e.target.value)}/></label>
    </div>

    {online&&<div className="metric-grid">
      <SummaryCard to={`/operations?view=expected&location_id=${encodeURIComponent(locationId)}&date=${date}`}><span>Expected</span><strong>{counts.expected}</strong></SummaryCard>
      <SummaryCard to={`/operations?view=completed&location_id=${encodeURIComponent(locationId)}&date=${date}`}><span>Completed</span><strong>{counts.completed}</strong></SummaryCard>
      <SummaryCard to={`/operations?view=pending&location_id=${encodeURIComponent(locationId)}&date=${date}`}><span>Pending</span><strong>{counts.pending}</strong></SummaryCard>
      <SummaryCard to={`/operations?view=required_pending&location_id=${encodeURIComponent(locationId)}&date=${date}`}><span>Required pending</span><strong>{counts.requiredPending}</strong></SummaryCard>
    </div>}

    {showManage&&canManage&&locationId!=='all'&&<div className="panel">
      <div className="section-heading"><div><h2>Checklist Setup</h2><p className="muted">Create recurring checklist items for the selected store.</p></div></div>
      <form className="form-grid" onSubmit={e=>{e.preventDefault();if(form.active_days.length)create.mutate()}}>
        <label>Category<select value={form.category} onChange={e=>setForm(old=>({...old,category:e.target.value as OperationsChecklistItem['category']}))}>{categories.map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Sort order<input type="number" min="0" value={form.sort_order} onChange={e=>setForm(old=>({...old,sort_order:Number(e.target.value)||0}))}/></label>
        <label className="span-2">Checklist item<input required maxLength={220} value={form.title} onChange={e=>setForm(old=>({...old,title:e.target.value}))} placeholder="Example: Verify front counter and lobby are ready"/></label>
        <label className="span-2">Instructions<textarea rows={2} value={form.description} onChange={e=>setForm(old=>({...old,description:e.target.value}))}/></label>
        <div className="span-2">
          <span className="muted">Active days</span>
          <div className="checkbox-grid">{weekdays.map(day=><label key={day.value}><input type="checkbox" checked={form.active_days.includes(day.value)} onChange={()=>toggleDay(day.value)}/>{day.label}</label>)}</div>
        </div>
        <label className="checkbox"><input type="checkbox" checked={form.required} onChange={e=>setForm(old=>({...old,required:e.target.checked}))}/>Required item</label>
        <div className="form-actions"><button disabled={create.isPending||!form.active_days.length}>{create.isPending?'Adding…':'Add Checklist Item'}</button></div>
        {create.error&&<p className="error span-2">{create.error instanceof Error?create.error.message:'Unable to add checklist item'}</p>}
      </form>

      <div className="section-heading"><h3>Recurring Items</h3><label className="checkbox"><input type="checkbox" checked={showInactive} onChange={e=>setShowInactive(e.target.checked)}/>Show inactive</label></div>
      {templates.data?.templates.length?<div className="table-wrap"><table>
        <thead><tr><th>Item</th><th>Category</th><th>Days</th><th>Required</th><th>Status</th><th></th></tr></thead>
        <tbody>{templates.data.templates.map(item=><tr key={item.id}>
          <td><strong>{item.title}</strong>{item.description&&<small className="issue-meta">{item.description}</small>}</td>
          <td>{item.category}</td>
          <td>{item.active_days.map(day=>weekdays.find(x=>x.value===day)?.label).join(', ')}</td>
          <td>{item.required?'Yes':'No'}</td>
          <td>{item.active?'Active':'Inactive'}</td>
          <td><button className="small-button secondary" disabled={toggle.isPending} onClick={()=>toggle.mutate(item)}>{item.active?'Deactivate':'Reactivate'}</button></td>
        </tr>)}</tbody>
      </table></div>:<p className="muted">No checklist items configured for this store yet.</p>}
    </div>}

    <div className="panel">
      <div className="section-heading"><div><h2>{checklist.data?.location.name??'Store'} Checklist</h2><span className="muted">{checklist.data?.date}</span></div><span>{counts.completed}/{counts.expected} completed</span></div>
      {checklist.isLoading?<p>Loading checklist…</p>:checklist.error?<p className="error">{checklist.error instanceof Error?checklist.error.message:'Unable to load checklist'}</p>:!grouped.length?<p className="empty-state">No checklist items match this view.{canManage&&locationId!=='all'?' Use Manage Checklist to add items.':''}</p>:grouped.map(([category,items])=><div key={category} className="ops-checklist-group">
        <h3>{category}</h3>
        {items.map(item=><div className={`ops-checklist-item ${item.completion?'is-done':''}`} key={item.id}>
          <div className="ops-checklist-copy">
            <div><strong>{item.title}</strong>{item.required&&<span className="required-badge">Required</span>}</div>
            {locationId==='all'&&<small>{item.store?.name} #{item.store?.store_number} · {item.checklist_date}</small>}
            {item.description&&<p>{item.description}</p>}
            {item.completion&&<small>{item.completion.status} by {item.completion.completed_by_name||'employee'} · {new Date(item.completion.completed_at).toLocaleString()}</small>}
          </div>
          <div className="button-row">
            {!item.completion&&<><button className="small-button" disabled={mark.isPending||(session?.employee.role!=='admin'&&item.location_id!==session?.location.id)} onClick={()=>mark.mutate({item,status:'Completed'})}>Complete</button><button className="small-button secondary" disabled={mark.isPending||(session?.employee.role!=='admin'&&item.location_id!==session?.location.id)} onClick={()=>mark.mutate({item,status:'Skipped'})}>Skip</button></>}
            {item.completion&&<button className="small-button secondary" disabled={reset.isPending||(session?.employee.role!=='admin'&&item.location_id!==session?.location.id)} onClick={()=>reset.mutate(item)}>Reset</button>}
          </div>
        </div>)}
      </div>)}
    </div>
  </section>
}
