import { useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, ApiError } from '../../api/http'
import { categories, channels, createIssue, getIssue, issueOptions, logCommunication, priorities, updateIssue, type CommunicationInput, type CustomerIssue, type IssueInput } from '../../api/issues'
import type { Customer, WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { useIssueQuery, useRefreshIssues } from './useIssues'
import { IssueTimeline } from './IssueTimeline'
import { displayTime, storeWallTime, wallTimeCandidates } from './time'

async function allCustomers(){const rows:Customer[]=[];for(let offset=0;;offset+=200){const result=await apiFetch<{customers:Customer[]}>(`/api/customers?limit=200&offset=${offset}`);rows.push(...result.customers);if(result.customers.length<200)return rows}}
async function matchingOrders(customerId:string,locationId:string){const rows:WorkOrder[]=[];for(let offset=0;;offset+=250){const result=await apiFetch<{orders:WorkOrder[]}>(`/api/orders?customer_id=${encodeURIComponent(customerId)}&location_id=${encodeURIComponent(locationId)}&limit=250&offset=${offset}`);rows.push(...result.orders);if(result.orders.length<250)return rows}}
function inputFrom(row:CustomerIssue):IssueInput{return {customer_id:row.customer_id,location_id:row.location_id,title:row.title,description:row.description,category:row.category,priority:row.priority,assigned_employee_id:row.assigned_employee_id,work_order_id:row.work_order_id,next_action:row.next_action,follow_up_date:row.follow_up_date}}

export function IssueEditor(){
 const {id}=useParams();const {online}=useOnline()
 const query=useIssueQuery(['detail',id],()=>getIssue(id!),!!id)
 if(id&&!query.data){return <section><h1>Customer issue</h1>{!online?<p className="offline-banner">Customer issues require an online connection.</p>:query.error?<p className="error" role="alert">{query.error.message} <button onClick={()=>void query.refetch()}>Retry case</button></p>:<p>Loading case…</p>}<Link to="/issues">Back to cases</Link></section>}
 return <IssueForm key={id||'new'} source={query.data}/>
}

function IssueForm({source}:{source?:CustomerIssue}){
 const {session}=useSession();const {online}=useOnline();const navigate=useNavigate();const refresh=useRefreshIssues()
 const [current,setCurrent]=useState(source)
 const [values,setValues]=useState<IssueInput>(()=>source?inputFrom(source):{customer_id:'',location_id:session?.location.id||'',title:'',description:'',category:'Customer Service',priority:'Normal',assigned_employee_id:null,work_order_id:null,next_action:'',follow_up_date:null})
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');const [conflict,setConflict]=useState<CustomerIssue|null>(null)
 const [resolution,setResolution]=useState(source?.resolution_summary||'');const [reopenReason,setReopenReason]=useState('')
 const timezone=current?.store?.timezone||session?.locations.find(l=>l.id===values.location_id)?.timezone||'America/New_York'
 const customers=useIssueQuery(['customer-choices'],allCustomers)
 const options=useIssueQuery(['options'],issueOptions)
 const orders=useIssueQuery(['order-choices',values.customer_id,values.location_id],()=>matchingOrders(values.customer_id,values.location_id),!!values.customer_id)
 const canWrite=online&&!!session&&(session.employee.role==='admin'||(current?.location_id||values.location_id)===session.location.id)
 const disabled=!canWrite||busy||!!conflict
 const [channel,setChannel]=useState('phone');const [occurred,setOccurred]=useState(()=>storeWallTime(timezone));const [occurrenceChoice,setOccurrenceChoice]=useState('')
 const [summary,setSummary]=useState('');const [updateFollowup,setUpdateFollowup]=useState(false);const [logNext,setLogNext]=useState('');const [logDue,setLogDue]=useState('')
 const pendingLog=useRef<CommunicationInput|null>(null);const [uncertainLog,setUncertainLog]=useState(false)
 const candidates=wallTimeCandidates(occurred,timezone)
 const eligibleEmployees=options.data?.employees.filter(e=>e.role==='admin'||!e.location_ids.length||e.location_ids.includes(values.location_id))||[]
 function change<K extends keyof IssueInput>(key:K,value:IssueInput[K]){setValues(old=>({...old,[key]:value,...(key==='customer_id'||key==='location_id'?{work_order_id:null}:{}),...(key==='location_id'?{assigned_employee_id:null}:{})}))}
 function saved(row:CustomerIssue){setCurrent(row);setValues(inputFrom(row));setResolution(row.resolution_summary);setConflict(null);setError('');void refresh()}
 function failure(e:unknown){if(e instanceof ApiError&&e.status===409&&e.current){setConflict(e.current as CustomerIssue);setError('Review the current case before saving again. Your unsaved text is preserved.')}else setError(e instanceof Error?e.message:'Unable to save')}
 async function save(event:FormEvent){event.preventDefault();if(disabled)return;setBusy(true);setError('');setNotice('');try{const row=current?await updateIssue(current.id,{...values,version:current.version}):await createIssue(values);saved(row);setNotice('Case saved.');if(!current)navigate(`/issues/${row.id}`,{replace:true})}catch(e){failure(e)}finally{setBusy(false)}}
 async function statusChange(resolve:boolean){if(disabled||!current)return;setBusy(true);setError('');setNotice('');try{const row=await updateIssue(current.id,resolve?{version:current.version,status:'Resolved',resolution_summary:resolution}:{version:current.version,status:'Open',reopen_reason:reopenReason});saved(row);setReopenReason('');setNotice(resolve?'Case resolved.':'Case reopened.')}catch(e){failure(e)}finally{setBusy(false)}}
 async function markProgress(status:string){if(disabled||!current)return;setBusy(true);setError('');try{saved(await updateIssue(current.id,{version:current.version,status}));setNotice('Status updated.')}catch(e){failure(e)}finally{setBusy(false)}}
 async function log(event:FormEvent){event.preventDefault();if(disabled||!current)return
  const instant=candidates.length===1?candidates[0]:candidates[Number(occurrenceChoice)]
  if(!pendingLog.current&&(!candidates.length||(candidates.length>1&&occurrenceChoice===''))){setError('Choose a valid occurrence time. Repeated daylight-saving times require an offset choice.');return}
  if(!pendingLog.current)pendingLog.current={operation_id:crypto.randomUUID(),channel,occurred_at:instant,summary,...(updateFollowup?{version:current.version,next_action:logNext,follow_up_date:logDue||null}:{})}
  setBusy(true);setError('');setNotice('')
  try{await logCommunication(current.id,pendingLog.current);pendingLog.current=null;setUncertainLog(false);setSummary('');setUpdateFollowup(false);setLogNext('');setLogDue('');setOccurred(storeWallTime(timezone));setOccurrenceChoice('');setNotice('Communication logged.');void refresh();try{saved(await getIssue(current.id))}catch{setNotice('Communication logged. Refresh the case before making further changes.')}}
  catch(e){if(e instanceof ApiError&&(e.status===0||e.status>=500)){setUncertainLog(true);setError('The result could not be confirmed. Retry this same communication to avoid duplicate entries.')}else{pendingLog.current=null;setUncertainLog(false);failure(e)}}finally{setBusy(false)}
 }
 return <section>
  <div className="page-heading"><div><h1>{current?'Customer issue':'New customer issue'}</h1>{current&&<p className="muted">{current.reference} · {current.status} · Updated {displayTime(current.updated_at,timezone)}</p>}</div><Link className="button secondary" to="/issues">Back to cases</Link></div>
  {!online&&<p className="offline-banner">Customer issues require an online connection. This previously loaded copy may be out of date.</p>}
  {online&&!canWrite&&<p className="offline-banner">Switch to {current?.store?.name||'the case store'} to update this case. You can read its history here.</p>}
  {source&&current&&source.version!==current.version&&source.version>current.version&&!conflict&&<p className="conflict-banner">This case has changed since you opened it. Your draft is preserved; saving will check for conflicts.</p>}
  {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status" className="issue-success">{notice}</p>}
  {conflict&&<div className="conflict-banner"><strong>Current case: {conflict.title} · {conflict.status}</strong><p className="issue-note">{conflict.description}</p><p>Next action: {conflict.next_action||'None'} · Follow-up: {conflict.follow_up_date||'None'}</p><button onClick={()=>saved(conflict)}>Load current case</button></div>}
  <form className="panel" onSubmit={save}><fieldset className="form-grid issue-fieldset" disabled={disabled||uncertainLog}>
   <label>Customer<select required value={values.customer_id} onChange={e=>change('customer_id',e.target.value)}><option value="">Select customer</option>{customers.data?.map(c=><option key={c.id} value={c.id}>{c.company||`${c.first_name} ${c.last_name}`.trim()||'Unnamed customer'}</option>)}{current?.customer&&!customers.data?.some(c=>c.id===current.customer_id)&&<option value={current.customer_id}>{current.customer.company||`${current.customer.first_name} ${current.customer.last_name}`}</option>}</select></label>
   <label>Store<select required value={values.location_id} onChange={e=>change('location_id',e.target.value)}>{session?.locations.filter(l=>session.employee.role==='admin'||l.id===session.location.id||l.id===current?.location_id).map(l=><option key={l.id} value={l.id}>{l.name} #{l.store_number}</option>)}</select></label>
   <div className="span-2 button-row"><Link target="_blank" rel="noopener noreferrer" to="/customers/new">Create customer in a new tab</Link>{current&&<Link to={`/customers/${current.customer_id}`}>View / edit customer</Link>}<button type="button" className="secondary" onClick={()=>void customers.refetch()}>Refresh customer choices</button><span className="muted">After creating a customer, refresh and select them here.</span></div>
   {current?.customer&&<p className="span-2 muted">Phone: {current.customer.phone||'Not provided'} · Email: {current.customer.email||'Not provided'}</p>}
   <label className="span-2">Case title<input required maxLength={200} value={values.title} onChange={e=>change('title',e.target.value)}/></label>
   <label className="span-2">Issue description<textarea required maxLength={10000} rows={4} value={values.description} onChange={e=>change('description',e.target.value)}/></label>
   <label>Category<select value={values.category} onChange={e=>change('category',e.target.value)}>{categories.map(x=><option key={x}>{x}</option>)}</select></label>
   <label>Priority<select value={values.priority} onChange={e=>change('priority',e.target.value)}>{priorities.map(x=><option key={x}>{x}</option>)}</select></label>
   <label>Assigned employee<select value={values.assigned_employee_id||''} onChange={e=>change('assigned_employee_id',e.target.value||null)}><option value="">Unassigned</option>{eligibleEmployees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}{current?.assignee&&!eligibleEmployees.some(e=>e.id===current.assigned_employee_id)&&<option value={current.assignee.id}>{current.assignee.name} (currently unavailable)</option>}</select></label>
   <label>Linked print order (optional)<select value={values.work_order_id||''} onChange={e=>change('work_order_id',e.target.value||null)}><option value="">No linked order</option>{orders.data?.map(o=><option key={o.id} value={o.id}>{o.order_number} · {o.description}</option>)}</select></label>
   {current?.work_order_id&&<p className="span-2"><Link to={`/orders/${current.work_order_id}`}>Open print order {current.order_number}</Link></p>}
   <label className="span-2">Next action<textarea maxLength={2000} rows={2} value={values.next_action} onChange={e=>change('next_action',e.target.value)}/></label>
   <label>Follow-up date<input type="date" value={values.follow_up_date||''} onChange={e=>change('follow_up_date',e.target.value||null)}/></label>
   <div className="form-actions span-2"><button disabled={disabled||uncertainLog}>{busy?'Saving…':'Save case'}</button></div>
  </fieldset>{customers.error&&<p className="error">Customer choices: {customers.error.message}</p>}{options.error&&<p className="error">Employee choices: {options.error.message}</p>}{orders.error&&<p className="error">Order choices: {orders.error.message}</p>}</form>
  {current&&<>
   <section className="panel"><h2>Case status</h2><fieldset className="issue-fieldset" disabled={disabled||uncertainLog}>
    {current.status!=='Resolved'?<><label>Status<select value={current.status} onChange={e=>void markProgress(e.target.value)}>{['Open','In Progress','Waiting on Customer','Waiting on Third Party'].map(x=><option key={x}>{x}</option>)}</select></label><label>Resolution summary<textarea maxLength={10000} rows={3} value={resolution} onChange={e=>setResolution(e.target.value)} placeholder="Record the outcome, refund, or replacement"/></label><button disabled={disabled||uncertainLog||!resolution.trim()} onClick={()=>void statusChange(true)}>Resolve case</button></>:<><p className="issue-note">{current.resolution_summary}</p><label>Reason for reopening<textarea maxLength={10000} rows={2} value={reopenReason} onChange={e=>setReopenReason(e.target.value)}/></label><button disabled={disabled||uncertainLog||!reopenReason.trim()} onClick={()=>void statusChange(false)}>Reopen case</button></>}
   </fieldset></section>
   <form className="panel" onSubmit={log}><h2>Log a communication</h2><p className="muted">Record a call, email, conversation, or note. This form only logs information.</p><fieldset className="form-grid issue-fieldset" disabled={disabled||uncertainLog}>
    <label>Communication channel<select value={channel} onChange={e=>setChannel(e.target.value)}>{channels.map(x=><option key={x}>{x}</option>)}</select></label>
    <label>Occurred at ({timezone})<input required type="datetime-local" value={occurred} onChange={e=>{setOccurred(e.target.value);setOccurrenceChoice('')}}/></label>
    {candidates.length===0&&<p className="error span-2">This time does not exist in the store timezone. Choose another time.</p>}
    {candidates.length>1&&<label className="span-2">Daylight-saving offset<select required value={occurrenceChoice} onChange={e=>setOccurrenceChoice(e.target.value)}><option value="">Choose which occurrence</option>{candidates.map((x,n)=><option key={x} value={String(n)}>{n===0?'First':'Second'} occurrence ({new Intl.DateTimeFormat('en-US',{timeZone:timezone,timeZoneName:'short'}).format(new Date(x))})</option>)}</select></label>}
    <label className="span-2">Communication summary<textarea required maxLength={10000} rows={4} value={summary} onChange={e=>setSummary(e.target.value)}/></label>
    <label className="checkbox span-2"><input type="checkbox" checked={updateFollowup} onChange={e=>{setUpdateFollowup(e.target.checked);setLogNext(current.next_action);setLogDue(current.follow_up_date||'')}}/>Update next action and follow-up with this log</label>
    {updateFollowup&&<><label>Next action after communication<textarea maxLength={2000} value={logNext} onChange={e=>setLogNext(e.target.value)}/></label><label>Next follow-up date<input type="date" value={logDue} onChange={e=>setLogDue(e.target.value)}/></label></>}
   </fieldset><button disabled={disabled}>{busy?'Saving…':uncertainLog?'Retry communication':'Log communication'}</button></form>
   <IssueTimeline id={current.id} timezone={timezone}/>
  </>}
 </section>
}
