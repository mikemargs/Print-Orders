import { apiFetch } from './http'
import type { OperationalTask } from './types'

export type TaskSummary = { open: number; overdue: number; high_priority: number; assigned_to_me: number }
export type TaskFilters = { search?: string; location_id?: string; status?: string; priority?: string; assigned_employee_id?: string; open_only?: boolean; limit?: number; offset?: number }
export type TaskOptions = {
  employees: { id: string; name: string; location_ids: string[]; role: string }[]
  customers: { id: string; company: string; first_name: string; last_name: string }[]
}

export async function listTasks(filters: TaskFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== false) params.set(key, String(value))
  })
  if (filters.open_only === false) params.set('open_only', 'false')
  return apiFetch<{ tasks: OperationalTask[]; total: number }>(`/api/tasks?${params}`)
}

export const getTaskSummary = () => apiFetch<TaskSummary>('/api/tasks/summary')
export const getTaskOptions = () => apiFetch<TaskOptions>('/api/tasks/options')
