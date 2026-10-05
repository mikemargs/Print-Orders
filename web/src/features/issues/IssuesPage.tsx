import { useState } from 'react'
import { Link } from 'react-router-dom'
import { categories, issueOptions, listIssues, priorities, statuses, type IssueFilters } from '../../api/issues'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { IssueSummary } from './IssueSummary'
import { useIssueQuery } from './useIssues'
import { overdue } from './time'
export function IssuesPage(){
 const {session}=useSession();const {online}=useOnline()
 const [filters,setFilters]=useState<IssueFilters>({unresolved_only:true});const [offset,setOffset]=useState(0)
 const query=useIssueQuery(['list',filters,offset],()=>listIssues({...filters,limit:50,offset}))
 const options=useIssueQuery(['options'],issueOptions)
 function change(name:keyof IssueFilters,value:string|boolean){setFilters(old=>({...old,[name]:value}));setOffset(0)}
 return <section>
  <div className="page-heading"><div><h1>Customer Issues</h1><p className="muted">Complaints, conversations, and follow-ups across all stores.</p></div>{online&&<Link className="button" to="/issues/new">New case</Link>}</div>
  {!online&&<p className="offline-banner">Customer issues require an online connection. Previously loaded cases may be out of date; editing is unavailable.</p>}
  <IssueSummary filters={filters}/>
  <div className="panel issue-filters">
   <label>Search cases<input value={filters.search||''} onChange={e=>change('search',e.target.value)} placeholder="Customer, case reference, or title"/></label>
   <label>Filter by store<select value={filters.location_id||''} onChange={e=>change('location_id',e.target.value)}><option value="">All stores</option>{session?.locations.map(l=><option key={l.id} value={l.id}>{l.name} #{l.store_number}</option>)}</select></label>
   <label>Filter by status<select value={filters.status||''} onChange={e=>{setFilters(old=>({...old,status:e.target.value,unresolved_only:!e.target.value}));setOffset(0)}}><option value="">All unresolved</option>{statuses.map(s=><option key={s}>{s}</option>)}</select></label>
   <label>Filter by priority<select value={filters.priority||''} onChange={e=>change('priority',e.target.value)}><option value="">Any priority</option>{priorities.map(s=><option key={s}>{s}</option>)}</select></label>
   <label>Filter by category<select value={filters.category||''} onChange={e=>change('category',e.target.value)}><option value="">Any category</option>{categories.map(s=><option key={s}>{s}</option>)}</select></label>
   <label>Filter by employee<select value={filters.assigned_employee_id||''} onChange={e=>change('assigned_employee_id',e.target.value)}><option value="">Any employee</option>{options.data?.employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
   <label className="checkbox"><input type="checkbox" checked={!filters.unresolved_only&&!filters.status} onChange={e=>{setFilters(old=>({...old,status:'',unresolved_only:!e.target.checked}));setOffset(0)}}/>Include resolved cases</label>
  </div>
  <div className="panel">
   {query.isLoading?<p>Loading customer issues…</p>:query.error?<p className="error" role="alert">{query.error.message} <button onClick={()=>void query.refetch()}>Retry cases</button></p>:query.data?<>
    <div className="section-heading"><h2>Cases</h2><span>{query.data.total} matching cases</span></div>
    {query.data.issues.length?<div className="table-wrap"><table><thead><tr><th>Case / Customer</th><th>Store</th><th>Status</th><th>Priority</th><th>Assigned</th><th>Follow-up / Next action</th></tr></thead><tbody>{query.data.issues.map(i=><tr key={i.id} className={overdue(i)?'overdue-row':undefined}>
     <td><Link to={`/issues/${i.id}`}>{i.title}</Link><small className="issue-meta">{i.reference}</small><span>{i.customer?.company||`${i.customer?.first_name||''} ${i.customer?.last_name||''}`}</span></td>
     <td>{i.store?.name} #{i.store?.store_number}</td><td>{i.status}</td><td><span className={`issue-priority ${i.priority.toLowerCase()}`}>{i.priority}</span></td><td>{i.assignee?.name||'Unassigned'}</td>
     <td>{i.follow_up_date||'No date'}{overdue(i)&&<strong className="issue-meta">Overdue</strong>}<small className="issue-meta">{i.next_action||'No next action'}</small></td>
    </tr>)}</tbody></table></div>:<p className="empty-state">No customer issues match these filters.</p>}
    <div className="button-row issue-pagination"><button className="secondary" disabled={offset===0||!online} onClick={()=>setOffset(x=>Math.max(0,x-50))}>Previous page</button><span>Page {Math.floor(offset/50)+1}</span><button className="secondary" disabled={offset+50>=query.data.total||!online} onClick={()=>setOffset(x=>x+50)}>Next page</button></div>
   </>:null}
  </div>
 </section>
}
