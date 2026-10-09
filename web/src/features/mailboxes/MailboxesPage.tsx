import { SummaryCard, ViewNotice, PageNavigation, useUrlValue, useUrlFlag, useListView } from '../../components/SummaryCard'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  createMailbox,
  getMailboxOptions,
  getMailboxSummary,
  listMailboxes,
  updateMailbox,
  type MailboxInput,
} from '../../api/mailboxes'
import type { MailboxRecord } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

const statuses = ['Active','Blocked','Closing','Closed'] as const
const forwardingStatuses = ['None','Scheduled','Active'] as const

function emptyForm(locationId:string,customerId=''):MailboxInput {
  return {
    location_id:locationId,
    customer_id:customerId,
    mailbox_number:'',
    status:'Active',
    renewal_date:null,
    balance_due:0,
    primary_id_on_file:false,
    secondary_id_on_file:false,
    form_1583_complete:false,
    msa_complete:false,
    phone_verified:false,
    forwarding_status:'None',
    forwarding_address:'',
    notes:'',
  }
}

export function MailboxesPage(){
  const {session}=useSession()
  const {online}=useOnline()
  const {view,offset}=useListView()
  const qc=useQueryClient()
  const [searchParams]=useSearchParams()
  const initialCustomerId=searchParams.get('customer_id')||''
  const [showForm,setShowForm]=useState(searchParams.get('new')==='1')
  const [editing,setEditing]=useState<MailboxRecord|null>(null)
  const [form,setForm]=useState<MailboxInput>(()=>emptyForm(session?.location.id||'',initialCustomerId))
  const [search,setSearch]=useUrlValue('search','')
  const [locationId,setLocationId]=useUrlValue('location_id','')
  const [status,setStatus]=useUrlValue('status','')
  const [customerId,setCustomerId]=useUrlValue('customer_id','')
  const [missingCompliance,setMissingCompliance]=useUrlFlag('missing_compliance')
  const [overdueOnly,setOverdueOnly]=useUrlFlag('overdue_only')

  const query=useQuery({
    queryKey:['mailboxes',view,offset,search,locationId,status,customerId,missingCompliance,overdueOnly],
    queryFn:()=>listMailboxes({
      view, offset,
      search,
      location_id:locationId,
      status,
      customer_id:customerId,
      missing_compliance:missingCompliance,
      overdue_only:overdueOnly,
      limit:250,
    }),
    enabled:online,
  })
  const summary=useQuery({queryKey:['mailbox-summary'],queryFn:getMailboxSummary,enabled:online})
  const options=useQuery({queryKey:['mailbox-options'],queryFn:getMailboxOptions,enabled:online})

  const save=useMutation({
    mutationFn:()=>editing
      ? updateMailbox(editing.id,{...form,version:editing.version})
      : createMailbox(form),
    onSuccess:async()=>{
      await qc.invalidateQueries({queryKey:['customer-profile-counts']})
      setEditing(null)
      setShowForm(false)
      setForm(emptyForm(session?.location.id||'',customerId))
      await qc.invalidateQueries({queryKey:['mailboxes']})
      await qc.invalidateQueries({queryKey:['mailbox-summary']})
      await qc.invalidateQueries({queryKey:['customer-profile-mailboxes']})
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

  function startEdit(row:MailboxRecord){
    setEditing(row)
    setForm({
      location_id:row.location_id,
      customer_id:row.customer_id,
      mailbox_number:row.mailbox_number,
      status:row.status,
      renewal_date:row.renewal_date,
      balance_due:row.balance_due,
      primary_id_on_file:row.primary_id_on_file,
      secondary_id_on_file:row.secondary_id_on_file,
      form_1583_complete:row.form_1583_complete,
      msa_complete:row.msa_complete,
      phone_verified:row.phone_verified,
      forwarding_status:row.forwarding_status,
      forwarding_address:row.forwarding_address,
      notes:row.notes,
    })
    setShowForm(true)
  }

  return <section><ViewNotice/>
    <div className="page-heading">
      <div><h1>Mailbox Management</h1><p className="muted">Renewals, compliance, blockers, forwarding, and customer mailbox records across all stores.</p></div>
      {online&&<button onClick={showForm?()=>{setShowForm(false);setEditing(null)}:startNew}>{showForm?'Close':'New Mailbox'}</button>}
    </div>

    {!online&&<div className="offline-banner">Mailbox Management requires an online connection.</div>}

    {online&&summary.data&&<div className="metric-grid">
      <SummaryCard to="/mailboxes?view=active"><span>Active mailboxes</span><strong>{summary.data.active}</strong></SummaryCard>
      <SummaryCard to="/mailboxes?view=overdue"><span>Overdue renewals</span><strong>{summary.data.overdue}</strong></SummaryCard>
      <SummaryCard to="/mailboxes?view=due_30"><span>Due within 30 days</span><strong>{summary.data.due_30}</strong></SummaryCard>
      <SummaryCard to="/mailboxes?view=missing_compliance"><span>Missing compliance</span><strong>{summary.data.missing_compliance}</strong></SummaryCard>
    </div>}

    {showForm&&online&&<form className="panel form-grid" onSubmit={e=>{e.preventDefault();save.mutate()}}>
      <div className="span-2 section-heading"><h2>{editing?`Edit Mailbox #${editing.mailbox_number}`:'New Mailbox'}</h2>{editing&&<span>Version {editing.version}</span>}</div>
      <label>Store<select required value={form.location_id} onChange={e=>setForm(old=>({...old,location_id:e.target.value}))}>{allowedStores?.map(store=><option key={store!.id} value={store!.id}>{store!.name} #{store!.store_number}</option>)}</select></label>
      <label>Mailbox #<input required maxLength={30} value={form.mailbox_number} onChange={e=>setForm(old=>({...old,mailbox_number:e.target.value}))}/></label>
      <label className="span-2">Customer<select required value={form.customer_id} onChange={e=>setForm(old=>({...old,customer_id:e.target.value}))}><option value="">Choose customer…</option>{options.data?.customers.map(customer=><option key={customer.id} value={customer.id}>{customer.company||`${customer.first_name} ${customer.last_name}`.trim()||'Unnamed customer'}</option>)}</select></label>
      <label>Status<select value={form.status} onChange={e=>setForm(old=>({...old,status:e.target.value}))}>{statuses.map(value=><option key={value}>{value}</option>)}</select></label>
      <label>Renewal date<input type="date" value={form.renewal_date||''} onChange={e=>setForm(old=>({...old,renewal_date:e.target.value||null}))}/></label>
      <label>Balance due ($)<input min="0" step="0.01" type="number" value={form.balance_due} onChange={e=>setForm(old=>({...old,balance_due:Number(e.target.value)||0}))}/></label>
      <label>Forwarding<select value={form.forwarding_status} onChange={e=>setForm(old=>({...old,forwarding_status:e.target.value,...(e.target.value==='None'?{forwarding_address:''}:{})}))}>{forwardingStatuses.map(value=><option key={value}>{value}</option>)}</select></label>
      {form.forwarding_status!=='None'&&<label className="span-2">Forwarding address<textarea required rows={2} value={form.forwarding_address} onChange={e=>setForm(old=>({...old,forwarding_address:e.target.value}))}/></label>}
      <fieldset className="span-2"><legend>Compliance checklist</legend><div className="checkbox-grid">
        <label><input type="checkbox" checked={form.primary_id_on_file} onChange={e=>setForm(old=>({...old,primary_id_on_file:e.target.checked}))}/> Primary ID on file</label>
        <label><input type="checkbox" checked={form.secondary_id_on_file} onChange={e=>setForm(old=>({...old,secondary_id_on_file:e.target.checked}))}/> Secondary ID on file</label>
        <label><input type="checkbox" checked={form.form_1583_complete} onChange={e=>setForm(old=>({...old,form_1583_complete:e.target.checked}))}/> USPS Form 1583 complete</label>
        <label><input type="checkbox" checked={form.msa_complete} onChange={e=>setForm(old=>({...old,msa_complete:e.target.checked}))}/> MSA complete</label>
        <label><input type="checkbox" checked={form.phone_verified} onChange={e=>setForm(old=>({...old,phone_verified:e.target.checked}))}/> Phone verified</label>
      </div></fieldset>
      <label className="span-2">Internal notes<textarea rows={3} value={form.notes} onChange={e=>setForm(old=>({...old,notes:e.target.value}))}/></label>
      {save.error&&<p className="error span-2">{save.error instanceof Error?save.error.message:'Unable to save mailbox'}</p>}
      <div className="form-actions span-2"><button disabled={save.isPending}>{save.isPending?'Saving…':editing?'Save Mailbox':'Create Mailbox'}</button><button type="button" className="secondary" onClick={()=>{setShowForm(false);setEditing(null)}}>Cancel</button></div>
    </form>}

    {customerId&&<div className="notice">Customer filter is active. <button className="link-button" onClick={()=>{setCustomerId('');setForm(old=>({...old,customer_id:''}))}}>Clear customer filter</button></div>}

    <div className="toolbar order-filters">
      <input placeholder="Search mailbox or customer…" value={search} onChange={e=>setSearch(e.target.value)}/>
      <select aria-label="Mailbox store filter" value={locationId} onChange={e=>setLocationId(e.target.value)}><option value="">All stores</option>{session?.locations.map(store=><option key={store.id} value={store.id}>{store.name} #{store.store_number}</option>)}</select>
      <select aria-label="Mailbox status filter" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{statuses.map(value=><option key={value}>{value}</option>)}</select>
      <label className="checkbox"><input type="checkbox" checked={overdueOnly} onChange={e=>setOverdueOnly(e.target.checked)}/>Overdue only</label>
      <label className="checkbox"><input type="checkbox" checked={missingCompliance} onChange={e=>setMissingCompliance(e.target.checked)}/>Missing compliance</label>
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Mailboxes</h2><span>{query.data?.total??0} matching</span></div>
      {query.isLoading?<p>Loading mailboxes…</p>:query.error?<p className="error">{query.error instanceof Error?query.error.message:'Unable to load mailboxes'}</p>:query.data?.mailboxes.length?<div className="table-wrap"><table>
        <thead><tr><th>Mailbox</th><th>Customer</th><th>Store</th><th>Status</th><th>Renewal</th><th>Compliance</th><th>Balance</th><th>Forwarding</th><th></th></tr></thead>
        <tbody>{query.data.mailboxes.map(row=>{
          const canEdit=session?.employee.role==='admin'||row.location_id===session?.location.id
          return <tr key={row.id} className={row.days_overdue>0?'overdue-row':undefined}>
            <td><strong>#{row.mailbox_number}</strong></td>
            <td>{row.customer?<Link to={`/customers/${row.customer.id}`}>{row.customer.company||`${row.customer.first_name} ${row.customer.last_name}`.trim()||'Customer'}</Link>:'—'}</td>
            <td>{row.store?`${row.store.name} #${row.store.store_number}`:'—'}</td>
            <td>{row.status}</td>
            <td>{row.renewal_date||'No date'}{row.days_overdue>0&&<small className="issue-meta">{row.days_overdue} days overdue</small>}</td>
            <td>{row.compliance_complete?<span className="artwork-status uploaded">Complete</span>:<span className="artwork-status missing">{row.missing_compliance.join(', ')}</span>}</td>
            <td>${Number(row.balance_due).toFixed(2)}</td>
            <td>{row.forwarding_status}{row.forwarding_status!=='None'&&<small className="issue-meta">{row.forwarding_address}</small>}</td>
            <td>{online&&canEdit&&<button className="small-button secondary" onClick={()=>startEdit(row)}>Edit</button>}</td>
          </tr>
        })}</tbody>
      </table></div>:<p className="empty-state">No mailboxes match these filters.</p>}
    </div>
    <PageNavigation total={query.data?.total} limit={250} count={query.data?.mailboxes.length??0}/>
  </section>
}
