import { Link } from 'react-router-dom'
import { getIssueSummary, type IssueFilters } from '../../api/issues'
import { useOnline } from '../../offline/OnlineState'
import { useIssueQuery } from './useIssues'
export function IssueSummary({filters={},compact=false}:{filters?:IssueFilters;compact?:boolean}){
 const {online}=useOnline();const query=useIssueQuery(['summary',filters],()=>getIssueSummary(filters))
 if(!online)return compact?<div className="panel"><Link to="/issues">Customer Issues</Link><p className="muted">Case summaries require an online connection.</p></div>:null
 return <div className={compact?'panel issue-summary':'issue-summary'}>
  {compact&&<div className="section-heading"><h2>Customer Issues</h2><Link to="/issues">View cases</Link></div>}
  {query.isLoading?<p>Loading case summary…</p>:query.error?<p role="alert" className="error">{query.error.message} <button onClick={()=>void query.refetch()}>Retry summary</button></p>:query.data&&<div className="metric-grid">
   <div className="metric"><span>Open cases</span><strong>{query.data.open}</strong></div>
   <div className="metric"><span>Overdue follow-ups</span><strong>{query.data.overdue}</strong></div>
   <div className="metric"><span>High / urgent</span><strong>{query.data.high_priority}</strong></div>
   <div className="metric"><span>Assigned to me</span><strong>{query.data.assigned_to_me}</strong></div>
  </div>}
 </div>
}
