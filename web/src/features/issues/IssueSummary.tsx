import { SummaryCard } from '../../components/SummaryCard'
import { Link } from 'react-router-dom'
import { getIssueSummary, type IssueFilters } from '../../api/issues'
import { useOnline } from '../../offline/OnlineState'
import { useIssueQuery } from './useIssues'
export function IssueSummary({filters={},compact=false}:{filters?:IssueFilters;compact?:boolean}){
 const target=(view:string)=>{const params=new URLSearchParams();Object.entries(filters).forEach(([key,value])=>{if(value!==undefined&&key!=='view')params.set(key,String(value))});params.set('view',view);return '/issues?'+params}
 const {online}=useOnline();const query=useIssueQuery(['summary',filters],()=>getIssueSummary(filters))
 if(!online)return compact?<div className="panel"><Link to="/issues">Customer Issues</Link><p className="muted">Case summaries require an online connection.</p></div>:null
 return <div className={compact?'panel issue-summary':'issue-summary'}>
  {compact&&<div className="section-heading"><h2>Customer Issues</h2><Link to="/issues">View cases</Link></div>}
  {query.isLoading?<p>Loading case summary…</p>:query.error?<p role="alert" className="error">{query.error.message} <button onClick={()=>void query.refetch()}>Retry summary</button></p>:query.data&&<div className="metric-grid">
   <SummaryCard to={target('open')}><span>Open cases</span><strong>{query.data.open}</strong></SummaryCard>
   <SummaryCard to={target('overdue')}><span>Overdue follow-ups</span><strong>{query.data.overdue}</strong></SummaryCard>
   <SummaryCard to={target('high_priority')}><span>High / urgent</span><strong>{query.data.high_priority}</strong></SummaryCard>
   <SummaryCard to={target('mine')}><span>Assigned to me</span><strong>{query.data.assigned_to_me}</strong></SummaryCard>
  </div>}
 </div>
}
