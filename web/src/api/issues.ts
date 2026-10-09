import { apiFetch } from './http'
import type { Customer, Employee, Location } from './types'
export const categories = ['Shipping','Print Order','Mailbox','Billing/Refund','Customer Service','Other'] as const
export const priorities = ['Low','Normal','High','Urgent'] as const
export const statuses = ['Open','In Progress','Waiting on Customer','Waiting on Third Party','Resolved'] as const
export const channels = ['phone','email','in person','internal note','other'] as const
export interface CustomerIssue {
 id:string;reference:string;version:number;customer_id:string;location_id:string;title:string;description:string;
 category:typeof categories[number];priority:typeof priorities[number];status:typeof statuses[number];
 assigned_employee_id:string|null;work_order_id:string|null;next_action:string;follow_up_date:string|null;resolution_summary:string;
 created_at:string;updated_at:string;resolved_at:string|null;created_by:string;updated_by:string;
 customer:Pick<Customer,'id'|'company'|'first_name'|'last_name'|'phone'|'email'>|null;
 store:Pick<Location,'id'|'name'|'store_number'|'timezone'>|null;assignee:Pick<Employee,'id'|'name'|'active'>|null;order_number:string|null
}
export interface IssueActivity {id:string;issue_id:string;activity_type:string;channel:string|null;occurred_at:string;recorded_at:string;author_name:string;summary:string;changed_fields:Record<string,{from:unknown;to:unknown}>}
export interface IssueFilters {view?:string;search?:string;location_id?:string;status?:string;priority?:string;category?:string;assigned_employee_id?:string;customer_id?:string;unresolved_only?:boolean;limit?:number;offset?:number}
export interface IssueSummary {open:number;overdue:number;high_priority:number;assigned_to_me:number}
export interface IssueInput {customer_id:string;location_id:string;title:string;description:string;category:string;priority:string;assigned_employee_id:string|null;work_order_id:string|null;next_action:string;follow_up_date:string|null}
export interface IssuePatch extends Partial<IssueInput> {version:number;status?:string;resolution_summary?:string;reopen_reason?:string}
export interface CommunicationInput {operation_id:string;channel:string;occurred_at:string;summary:string;version?:number;next_action?:string;follow_up_date?:string|null}
function qs(filters:IssueFilters){const query=new URLSearchParams();Object.entries(filters).forEach(([key,value])=>{if(value!==undefined&&value!=='')query.set(key,String(value))});return query.toString()}
export const listIssues=(filters:IssueFilters)=>apiFetch<{issues:CustomerIssue[];total:number}>(`/api/issues?${qs(filters)}`)
export const getIssue=(id:string)=>apiFetch<CustomerIssue>(`/api/issues/${id}`)
export const createIssue=(input:IssueInput)=>apiFetch<CustomerIssue>('/api/issues',{method:'POST',body:JSON.stringify(input)})
export const updateIssue=(id:string,input:IssuePatch)=>apiFetch<CustomerIssue>(`/api/issues/${id}`,{method:'PATCH',body:JSON.stringify(input)})
export const listActivities=(id:string,offset=0)=>apiFetch<{activities:IssueActivity[];total:number}>(`/api/issues/${id}/activities?limit=50&offset=${offset}`)
export const logCommunication=(id:string,input:CommunicationInput)=>apiFetch<IssueActivity>(`/api/issues/${id}/activities`,{method:'POST',body:JSON.stringify(input)})
export const getIssueSummary=(filters:IssueFilters={})=>apiFetch<IssueSummary>(`/api/issues/summary?${qs(filters)}`)
export const issueOptions=()=>apiFetch<{employees:Employee[]}>('/api/issues/options')
