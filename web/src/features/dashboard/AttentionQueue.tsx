import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listIssues } from '../../api/issues'
import { listTasks } from '../../api/tasks'
import type { WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { storeDate } from '../issues/time'

type AttentionItem = {
  key: string
  type: 'Print Order' | 'Task' | 'Customer Issue'
  title: string
  store: string
  due: string
  priority: string
  href: string
  rank: number
}

function dueRank(due: string, today: string) {
  if (!due) return 3
  if (due < today) return 0
  if (due === today) return 1
  return 3
}

export function AttentionQueue({orders}:{orders:WorkOrder[]}) {
  const {session}=useSession()
  const {online}=useOnline()
  const tasks=useQuery({queryKey:['dashboard-attention-tasks'],queryFn:()=>listTasks({open_only:true,limit:250}),enabled:online})
  const issues=useQuery({queryKey:['dashboard-attention-issues'],queryFn:()=>listIssues({unresolved_only:true,limit:250,offset:0}),enabled:online})
  const locationMap=new Map((session?.locations??[]).map(location=>[location.id,location]))
  const items:AttentionItem[]=[]

  for(const order of orders){
    const location=locationMap.get(order.location_id)
    const today=storeDate(location?.timezone||'America/New_York')
    const urgent=order.priority==='Rush'
    if(!(urgent||(order.due_date&&order.due_date<=today)))continue
    items.push({
      key:`order-${order.id}`,
      type:'Print Order',
      title:`${order.order_number} · ${order.description||'Print order'}`,
      store:location?`${location.name} #${location.store_number}`:'Unknown store',
      due:order.due_date||'No due date',
      priority:order.priority,
      href:`/orders/${order.id}`,
      rank:Math.min(dueRank(order.due_date,today),urgent?2:3),
    })
  }

  for(const task of tasks.data?.tasks??[]){
    const today=storeDate(task.store?.timezone||'America/New_York')
    const urgent=['High','Urgent'].includes(task.priority)
    if(!(urgent||(task.due_date&&task.due_date<=today)))continue
    items.push({
      key:`task-${task.id}`,
      type:'Task',
      title:task.title,
      store:task.store?`${task.store.name} #${task.store.store_number}`:'Unknown store',
      due:task.due_date||'No due date',
      priority:task.priority,
      href:task.customer_id?`/tasks?customer_id=${task.customer_id}`:'/tasks',
      rank:Math.min(dueRank(task.due_date||'',today),task.priority==='Urgent'?1:urgent?2:3),
    })
  }

  for(const issue of issues.data?.issues??[]){
    const today=storeDate(issue.store?.timezone||'America/New_York')
    const urgent=['High','Urgent'].includes(issue.priority)
    if(!(urgent||(issue.follow_up_date&&issue.follow_up_date<=today)))continue
    items.push({
      key:`issue-${issue.id}`,
      type:'Customer Issue',
      title:`${issue.reference} · ${issue.title}`,
      store:issue.store?`${issue.store.name} #${issue.store.store_number}`:'Unknown store',
      due:issue.follow_up_date||'No follow-up date',
      priority:issue.priority,
      href:`/issues/${issue.id}`,
      rank:Math.min(dueRank(issue.follow_up_date||'',today),issue.priority==='Urgent'?1:urgent?2:3),
    })
  }

  items.sort((a,b)=>a.rank-b.rank||a.due.localeCompare(b.due)||a.title.localeCompare(b.title))
  const visible=items.slice(0,12)

  return <div className="panel attention-queue">
    <div className="section-heading"><div><h2>Needs Attention</h2><p className="muted">Overdue, due today, rush, high-priority, and urgent work across all stores.</p></div><strong>{items.length}</strong></div>
    {!visible.length?<p className="empty-state">Nothing currently needs immediate attention.</p>:<div className="table-wrap"><table>
      <thead><tr><th>Type</th><th>Item</th><th>Store</th><th>Due / Follow-up</th><th>Priority</th></tr></thead>
      <tbody>{visible.map(item=><tr key={item.key} className={item.rank===0?'overdue-row':undefined}>
        <td>{item.type}</td><td><Link to={item.href}>{item.title}</Link></td><td>{item.store}</td><td>{item.due}</td><td>{item.priority}</td>
      </tr>)}</tbody>
    </table></div>}
    {items.length>visible.length&&<p className="muted">Showing the 12 most urgent items.</p>}
    {!online&&<p className="muted">Offline mode shows cached print-order attention only; tasks and customer issues require a connection.</p>}
  </div>
}
