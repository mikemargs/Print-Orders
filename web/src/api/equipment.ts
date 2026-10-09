import { apiFetch } from './http'
import type { EquipmentAssetRecord, EquipmentServiceEventRecord } from './types'

export const equipmentStatuses = ['Operational','Needs Attention','Out of Service','Retired'] as const
export const equipmentEventTypes = ['Maintenance','Repair','Inspection','Service Call','Issue Reported','Other'] as const

export type EquipmentSummary = {
  active_assets: number
  needs_attention: number
  out_of_service: number
  service_overdue: number
  service_due_30: number
  stores: { location_id: string; store: string; active_assets: number; needs_attention: number; out_of_service: number; service_overdue: number }[]
}

export type EquipmentFilters = {
  view?:string;
  search?: string
  location_id?: string
  category?: string
  status?: string
  attention_only?: boolean
  include_retired?: boolean
  limit?: number
  offset?: number
}

export type EquipmentInput = {
  location_id: string
  name: string
  category: string
  asset_tag: string
  manufacturer: string
  model: string
  serial_number: string
  status: EquipmentAssetRecord['status']
  purchase_date: string | null
  warranty_expiration: string | null
  vendor: string
  service_provider: string
  next_service_date: string | null
  notes: string
  active: boolean
}

function qs(filters: EquipmentFilters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key,value]) => {
    if (value !== undefined && value !== '' && value !== false) params.set(key,String(value))
  })
  return params.toString()
}

export const listEquipment = (filters: EquipmentFilters = {}) =>
  apiFetch<{equipment:EquipmentAssetRecord[];total:number}>(`/api/equipment?${qs(filters)}`)

export const getEquipmentSummary = () => apiFetch<EquipmentSummary>('/api/equipment/summary')

export const createEquipment = (input:EquipmentInput) =>
  apiFetch<EquipmentAssetRecord>('/api/equipment',{method:'POST',body:JSON.stringify(input)})

export const updateEquipment = (id:string,input:EquipmentInput&{version:number}) =>
  apiFetch<EquipmentAssetRecord>(`/api/equipment/${id}`,{method:'PATCH',body:JSON.stringify(input)})

export const reportEquipmentIssue = (item:EquipmentAssetRecord,summary:string) =>
  apiFetch<EquipmentAssetRecord>(`/api/equipment/${item.id}/report-issue`,{
    method:'POST',
    body:JSON.stringify({version:item.version,summary}),
  })

export const addEquipmentService = (
  item:EquipmentAssetRecord,
  input:{
    event_date:string
    event_type:EquipmentServiceEventRecord['event_type']
    summary:string
    provider:string
    cost:number
    status_after:EquipmentAssetRecord['status']|null
    next_service_date:string|null
  }
) => apiFetch<{equipment:EquipmentAssetRecord;event:EquipmentServiceEventRecord}>(`/api/equipment/${item.id}/service-events`,{
  method:'POST',
  body:JSON.stringify({version:item.version,...input}),
})

export const getEquipmentHistory = (id:string) =>
  apiFetch<{events:EquipmentServiceEventRecord[]}>(`/api/equipment/${id}/history`)
