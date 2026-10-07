import { apiFetch } from './http'
import type { OperationsChecklistItem } from './types'

export type OperationsSummary = {
  expected: number; completed: number; skipped: number; pending: number; required_pending: number;
  stores: { location_id: string; store: string; date: string; expected: number; completed: number; skipped: number; pending: number; required_pending: number }[];
}

export type ChecklistResponse = {
  location: { id: string; name: string; store_number: string; timezone: string };
  date: string;
  items: OperationsChecklistItem[];
}

export type ChecklistTemplateInput = {
  location_id: string; title: string; description: string; category: OperationsChecklistItem['category'];
  active_days: number[]; required: boolean; active: boolean; sort_order: number;
}

export const getOperationsChecklist = (locationId: string, date: string) =>
  apiFetch<ChecklistResponse>(`/api/operations/checklist?location_id=${encodeURIComponent(locationId)}&checklist_date=${encodeURIComponent(date)}`)

export const getOperationsSummary = () => apiFetch<OperationsSummary>('/api/operations/summary')

export const listOperationsTemplates = (locationId = '', includeInactive = false) => {
  const params = new URLSearchParams()
  if (locationId) params.set('location_id', locationId)
  if (includeInactive) params.set('include_inactive', 'true')
  return apiFetch<{ templates: OperationsChecklistItem[] }>(`/api/operations/templates?${params}`)
}

export const createOperationsTemplate = (body: ChecklistTemplateInput) =>
  apiFetch<OperationsChecklistItem>('/api/operations/templates', { method: 'POST', body: JSON.stringify(body) })

export const updateOperationsTemplate = (item: OperationsChecklistItem, values: ChecklistTemplateInput) =>
  apiFetch<OperationsChecklistItem>(`/api/operations/templates/${item.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ ...values, version: item.version }),
  })

export const completeOperationsItem = (item: OperationsChecklistItem, date: string, status: 'Completed' | 'Skipped', notes = '') =>
  apiFetch<OperationsChecklistItem>(`/api/operations/checklist/${item.id}`, {
    method: 'PUT',
    body: JSON.stringify({ checklist_date: date, status, notes, version: item.completion?.version ?? null }),
  })

export const resetOperationsItem = (item: OperationsChecklistItem, date: string) =>
  apiFetch<void>(`/api/operations/checklist/${item.id}?checklist_date=${encodeURIComponent(date)}`, { method: 'DELETE' })
