import { SummaryCard, ViewNotice, PageNavigation, useUrlValue, useUrlFlag, useListView } from '../../components/SummaryCard'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  createShippingCase,
  getShippingOptions,
  getShippingSummary,
  listShippingCases,
  shippingCaseTypes,
  shippingStatuses,
  updateShippingCase,
  type ShippingCaseInput,
} from '../../api/shipping'
import type { ShippingCaseRecord } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

function emptyForm(locationId:string,customerId=''):ShippingCaseInput {
  return {
    location_id:locationId,
    customer_id:customerId,
    customer_issue_id:null,
    tracking_number:'',
    carrier:'UPS',
    service_level:'',
    case_type:'Late Delivery',
    status:'Open',
    ship_date:null,
    promised_date:null,
    delivered_date:null,
    carrier_reference:'',
    amount_requested:0,
    amount_approved:0,
    next_action:'',
    follow_up_date:null,
    notes:'',
  }
}

export function ShippingCasesPage(){
  const {session}=useSession()
  const {online}=useOnline()
  const {view,offset}=useListView()
  const qc=useQueryClient()
  const [searchParams]=useSearchParams()
  const initialCustomerId=searchParams.get('customer_id')||''
  const [showForm,setShowForm]=useState(searchParams.get('new')==='1')
  const [editing,setEditing]=useState<ShippingCaseRecord|null>(null)
  const [form,setForm]=useState<ShippingCaseInput>(()=>emptyForm(session?.location.id||'',initialCustomerId))
  const [search,setSearch]=useUrlValue('search','')
  const [locationId,setLocationId]=useUrlValue('location_id','')
  const [customerId,setCustomerId]=useUrlValue('customer_id','')
  const [status,setStatus]=useUrlValue('status','')
  const [caseType,setCaseType]=useUrlValue('case_type','')
  const [includeClosed,setIncludeClosed]=useUrlFlag('include_closed')

  const query=useQuery({
    queryKey:['shipping-cases',view,offset,search,locationId,customerId,status,caseType,includeClosed],
    queryFn:()=>listShippingCases({
      view, offset,
      search,
      location_id:locationId,
      customer_id:customerId,
      status,
      case_type:caseType,
      open_only:!includeClosed&&!status,
      limit:250,
    }),
    enabled:online,
  })
  const summary=useQuery({queryKey:['shipping-summary'],queryFn:getShippingSummary,enabled:online})
  const options=useQuery({queryKey:['shipping-options'],queryFn:getShippingOptions,enabled:online})
  const eligibleIssues=useMemo(
    ()=>(options.data?.issues??[]).filter(issue=>issue.customer_id===form.customer_id&&issue.location_id===form.location_id),
    [options.data?.issues,form.customer_id,form.location_id],
  )

  const save=useMutation({
    mutationFn:()=>editing
      ? updateShippingCase(editing.id,{...form,version:editing.version})
      : createShippingCase(form),
    onSuccess:async()=>{
      await qc.invalidateQueries({queryKey:['customer-profile-counts']})
      setEditing(null)
      setShowForm(false)
      setForm(emptyForm(session?.location.id||'',customerId))
      await qc.invalidateQueries({queryKey:['shipping-cases']})
      await qc.invalidateQueries({queryKey:['shipping-summary']})
      await qc.invalidateQueries({queryKey:['customer-profile-shipping']})
      await qc.invalidateQueries({queryKey:['dashboard-attention-shipping']})
    },
  })

  const allowedStores=session?.employee.role==='admin'
    ? session.locations
    : [session?.location].filter(Boolean)

  function startNew(){
    setEditing(null)
    setForm(emptyForm(session?.location.id||'',customerId))
    setShowForm(true)
  }

  function startEdit(row:ShippingCaseRecord){
    setEditing(row)
    setForm({
      location_id:row.location_id,
      customer_id:row.customer_id,
      customer_issue_id:row.customer_issue_id,
      tracking_number:row.tracking_number,
      carrier:row.carrier,
      service_level:row.service_level,
      case_type:row.case_type,
      status:row.status,
      ship_date:row.ship_date,
      promised_date:row.promised_date,
      delivered_date:row.delivered_date,
      carrier_reference:row.carrier_reference,
      amount_requested:row.amount_requested,
      amount_approved:row.amount_approved,
      next_action:row.next_action,
      follow_up_date:row.follow_up_date,
      notes:row.notes,
    })
    setShowForm(true)
  }

  return <section><ViewNotice/>
    <div className="page-heading">
      <div><h1>Shipping, Claims & GSR</h1><p className="muted">Track service failures, claims, carrier follow-ups, approvals, and refunds across all stores.</p></div>
      {online&&<button onClick={showForm?()=>{setShowForm(false);setEditing(null)}:startNew}>{showForm?'Close':'New Shipping Case'}</button>}
    </div>

    {!online&&<div className="offline-banner">Shipping, Claims & GSR tracking requires an online connection.</div>}

    {online&&summary.data&&<div className="metric-grid">
      <SummaryCard to="/shipping?view=open"><span>Open cases</span><strong>{summary.data.open}</strong></SummaryCard>
      <SummaryCard to="/shipping?view=overdue"><span>Overdue follow-ups</span><strong>{summary.data.overdue_followups}</strong></SummaryCard>
      <SummaryCard to="/shipping?view=gsr"><span>GSR pending</span><strong>{summary.data.gsr_pending}</strong></SummaryCard>
      <SummaryCard to="/shipping?view=claims"><span>Claims pending</span><strong>{summary.data.claims_pending}</strong></SummaryCard>
    </div>}

    {showForm&&online&&<form className="panel form-grid" onSubmit={e=>{e.preventDefault();save.mutate()}}>
      <div className="span-2 section-heading"><h2>{editing?'Edit Shipping Case':'New Shipping Case'}</h2>{editing&&<span>Version {editing.version}</span>}</div>
      <label>Store<select required value={form.location_id} onChange={e=>setForm(old=>({...old,location_id:e.target.value,customer_issue_id:null}))}>{allowedStores?.map(store=><option key={store!.id} value={store!.id}>{store!.name} #{store!.store_number}</option>)}</select></label>
      <label>Case type<select value={form.case_type} onChange={e=>setForm(old=>({...old,case_type:e.target.value}))}>{shippingCaseTypes.map(value=><option key={value}>{value}</option>)}</select></label>
      <label className="span-2">Customer<select required value={form.customer_id} onChange={e=>setForm(old=>({...old,customer_id:e.target.value,customer_issue_id:null}))}><option value="">Choose customer…</option>{options.data?.customers.map(customer=><option key={customer.id} value={customer.id}>{customer.company||`${customer.first_name} ${customer.last_name}`.trim()||'Unnamed customer'}</option>)}</select></label>
      <label>Tracking number<input required maxLength={120} value={form.tracking_number} onChange={e=>setForm(old=>({...old,tracking_number:e.target.value}))}/></label>
      <label>Service level<input maxLength={120} placeholder="Next Day Air, Ground…" value={form.service_level} onChange={e=>setForm(old=>({...old,service_level:e.target.value}))}/></label>
      <label>Carrier<input required maxLength={60} value={form.carrier} onChange={e=>setForm(old=>({...old,carrier:e.target.value}))}/></label>
      <label>Status<select value={form.status} onChange={e=>setForm(old=>({...old,status:e.target.value}))}>{shippingStatuses.map(value=><option key={value}>{value}</option>)}</select></label>
      <label>Ship date<input type="date" value={form.ship_date||''} onChange={e=>setForm(old=>({...old,ship_date:e.target.value||null}))}/></label>
      <label>Promised date<input type="date" value={form.promised_date||''} onChange={e=>setForm(old=>({...old,promised_date:e.target.value||null}))}/></label>
      <label>Delivered date<input type="date" value={form.delivered_date||''} onChange={e=>setForm(old=>({...old,delivered_date:e.target.value||null}))}/></label>
      <label>Follow-up date<input type="date" value={form.follow_up_date||''} onChange={e=>setForm(old=>({...old,follow_up_date:e.target.value||null}))}/></label>
      <label>Carrier / claim reference<input maxLength={160} value={form.carrier_reference} onChange={e=>setForm(old=>({...old,carrier_reference:e.target.value}))}/></label>
      <label>Linked Customer Issue<select value={form.customer_issue_id||''} onChange={e=>setForm(old=>({...old,customer_issue_id:e.target.value||null}))}><option value="">None</option>{eligibleIssues.map(issue=><option key={issue.id} value={issue.id}>{issue.reference} · {issue.title}</option>)}</select></label>
      <label>Amount requested ($)<input min="0" step="0.01" type="number" value={form.amount_requested} onChange={e=>setForm(old=>({...old,amount_requested:Number(e.target.value)||0}))}/></label>
      <label>Amount approved ($)<input min="0" step="0.01" type="number" value={form.amount_approved} onChange={e=>setForm(old=>({...old,amount_approved:Number(e.target.value)||0}))}/></label>
      <label className="span-2">Next action<textarea rows={2} maxLength={2000} value={form.next_action} onChange={e=>setForm(old=>({...old,next_action:e.target.value}))}/></label>
      <label className="span-2">Internal notes<textarea rows={3} maxLength={10000} value={form.notes} onChange={e=>setForm(old=>({...old,notes:e.target.value}))}/></label>
      {save.error&&<p className="error span-2">{save.error instanceof Error?save.error.message:'Unable to save shipping case'}</p>}
      <div className="form-actions span-2"><button disabled={save.isPending}>{save.isPending?'Saving…':editing?'Save Case':'Create Case'}</button><button type="button" className="secondary" onClick={()=>{setShowForm(false);setEditing(null)}}>Cancel</button></div>
    </form>}

    {customerId&&<div className="notice">Customer filter is active. <button className="link-button" onClick={()=>{setCustomerId('');setForm(old=>({...old,customer_id:''}))}}>Clear customer filter</button></div>}

    <div className="toolbar order-filters">
      <input placeholder="Tracking, reference, customer…" value={search} onChange={e=>setSearch(e.target.value)}/>
      <select aria-label="Shipping store filter" value={locationId} onChange={e=>setLocationId(e.target.value)}><option value="">All stores</option>{session?.locations.map(store=><option key={store.id} value={store.id}>{store.name} #{store.store_number}</option>)}</select>
      <select aria-label="Shipping type filter" value={caseType} onChange={e=>setCaseType(e.target.value)}><option value="">All case types</option>{shippingCaseTypes.map(value=><option key={value}>{value}</option>)}</select>
      <select aria-label="Shipping status filter" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All open statuses</option>{shippingStatuses.map(value=><option key={value}>{value}</option>)}</select>
      <label className="checkbox"><input type="checkbox" checked={includeClosed} onChange={e=>setIncludeClosed(e.target.checked)}/>Include closed</label>
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Shipping Cases</h2><span>{query.data?.total??0} matching</span></div>
      {query.isLoading?<p>Loading shipping cases…</p>:query.error?<p className="error">{query.error instanceof Error?query.error.message:'Unable to load shipping cases'}</p>:query.data?.cases.length?<div className="table-wrap"><table>
        <thead><tr><th>Tracking / Customer</th><th>Store</th><th>Type</th><th>Status</th><th>Follow-up</th><th>Reference</th><th>Amounts</th><th>Next action</th><th></th></tr></thead>
        <tbody>{query.data.cases.map(row=>{
          const canEdit=session?.employee.role==='admin'||row.location_id===session?.location.id
          const overdue=row.follow_up_date&&row.follow_up_date<new Date().toISOString().slice(0,10)&&!['Denied','Refunded','Resolved'].includes(row.status)
          return <tr key={row.id} className={overdue?'overdue-row':undefined}>
            <td><strong>{row.tracking_number}</strong>{row.customer&&<small className="issue-meta"><Link to={`/customers/${row.customer.id}`}>{row.customer.company||`${row.customer.first_name} ${row.customer.last_name}`.trim()||'Customer'}</Link></small>}<small className="issue-meta">{row.carrier} {row.service_level}</small></td>
            <td>{row.store?`${row.store.name} #${row.store.store_number}`:'—'}</td>
            <td>{row.case_type}</td><td>{row.status}</td>
            <td>{row.follow_up_date||'No date'}{overdue&&<small className="issue-meta">Overdue</small>}</td>
            <td>{row.carrier_reference||'—'}{row.customer_issue_id&&<small className="issue-meta"><Link to={`/issues/${row.customer_issue_id}`}>{row.issue_reference}</Link></small>}</td>
            <td>${Number(row.amount_requested).toFixed(2)} requested<small className="issue-meta">${Number(row.amount_approved).toFixed(2)} approved</small></td>
            <td>{row.next_action||'—'}</td>
            <td>{online&&canEdit&&<button className="small-button secondary" onClick={()=>startEdit(row)}>Edit</button>}</td>
          </tr>
        })}</tbody>
      </table></div>:<p className="empty-state">No shipping cases match these filters.</p>}
    </div>
    <PageNavigation total={query.data?.total} limit={250} count={query.data?.cases.length??0}/>
  </section>
}
