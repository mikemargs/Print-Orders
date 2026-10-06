import { apiFetch } from './http'
import type { Customer, Employee, Location } from './types'

export const taskStatuses = ['Open','In Progress','Waiting','Completed','Cancelled'] as const
export const taskPriorities = ['Normal','High','Urgent'] as const

export interface OperationsTask {
  id:string;version:number;location_id:string;title:string;description:string;
  status:typeof taskStatuses[number];priority:typeof taskPriorities[number];
  assigned_employee_id:string|null;due_date:string|null;customer_id:string|null;
  work_order_id:string|null;issue_id:string|null;created_by:string;updated_by:string;
  created_at:string;updated_at:string;completed_at:string|null;
  store:Pick<Location,'id'|'name'|'store_number'|'timezone'>|null;
  assignee:Pick<Employee,'id'|'name'|'active'>|null;
  customer:Pick<Customer,'id'|'company'|'first_name'|'last_name'>|null;
  order:{id:string;order_number:string;description:string}|null;
  issue:{id:string;reference:string;title:string}|null;
}
export interface TaskInput {
  location_id:string;title:string;description:string;status:string;priority:string;
  assigned_employee_id:string|null;due_date:string|null;customer_id:string|null;
  work_order_id:string|null;issue_id:string|null;
}
export interface TaskPatch extends Partial<TaskInput> {version:number}
export interface TaskFilters {
  search?:string;location_id?:string;status?:string;priority?:string;
  assigned_employee_id?:string;customer_id?:string;open_only?:boolean;limit?:number;offset?:number
}
export interface TaskSummary {open:number;overdue:number;due_today:number;assigned_to_me:number}

function qs(filters:TaskFilters){
  const query=new URLSearchParams()
  Object.entries(filters).forEach(([key,value])=>{
    if(value!==undefined&&value!=='')query.set(key,String(value))
  })
  return query.toString()
}
export const listTasks=(filters:TaskFilters)=>apiFetch<{tasks:OperationsTask[];total:number}>(`/api/tasks?${qs(filters)}`)
export const getTask=(id:string)=>apiFetch<OperationsTask>(`/api/tasks/${id}`)
export const createTask=(input:TaskInput)=>apiFetch<OperationsTask>('/api/tasks',{method:'POST',body:JSON.stringify(input)})
export const updateTask=(id:string,input:TaskPatch)=>apiFetch<OperationsTask>(`/api/tasks/${id}`,{method:'PATCH',body:JSON.stringify(input)})
export const getTaskSummary=(filters:TaskFilters={})=>apiFetch<TaskSummary>(`/api/tasks/summary?${qs(filters)}`)
export const taskOptions=()=>apiFetch<{employees:Employee[]}>('/api/tasks/options')
