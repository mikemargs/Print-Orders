import { useInfiniteQuery } from '@tanstack/react-query'
import { listActivities } from '../../api/issues'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { displayTime } from './time'
const fieldLabels:Record<string,string>={title:'Title',description:'Description',status:'Status',priority:'Priority',category:'Category',next_action:'Next action',follow_up_date:'Follow-up date',resolution_summary:'Resolution',assigned_employee_id:'Assigned employee',customer_id:'Customer',location_id:'Store',work_order_id:'Linked work order'}
export function IssueTimeline({id,timezone}:{id:string;timezone:string}){
 const {session}=useSession();const {online}=useOnline()
 const query=useInfiniteQuery({queryKey:['issues',session?.company.id,session?.employee.id,session?.location.id,'activities',id],queryFn:({pageParam})=>listActivities(id,pageParam),initialPageParam:0,getNextPageParam:(page,_pages,lastOffset)=>lastOffset+page.activities.length<page.total?lastOffset+page.activities.length:undefined,enabled:online&&!!session,refetchInterval:online?30_000:false,refetchIntervalInBackground:false,refetchOnWindowFocus:true})
 return <section className="panel"><div className="section-heading"><h2>Communication &amp; case history</h2><span className="muted">{timezone}</span></div>
 {query.isLoading?<p>Loading history…</p>:query.error?<p className="error" role="alert">{query.error.message} <button onClick={()=>void query.refetch()}>Retry history</button></p>:query.data?<>
  <ol className="issue-timeline">{query.data.pages.flatMap(p=>p.activities).map(a=><li key={a.id}>
   <div className="section-heading"><strong>{a.activity_type==='communication'?a.channel:'Case change'}</strong><span>{displayTime(a.occurred_at,timezone)}</span></div>
   <p className="issue-note">{a.summary}</p>
   {Object.entries(a.changed_fields).map(([field,value])=><p key={field} className="muted issue-note">{fieldLabels[field]||field}: {field.endsWith('_id')?'Updated':`${value.from??'—'} → ${value.to??'—'}`}</p>)}
   <small className="muted">Logged by {a.author_name} · {displayTime(a.recorded_at,timezone)}</small>
  </li>)}</ol>
  {query.hasNextPage&&<button className="secondary" disabled={query.isFetchingNextPage||!online} onClick={()=>void query.fetchNextPage()}>Load more history</button>}
 </>:!online?<p className="muted">Connect to load case history.</p>:null}
 </section>
}
