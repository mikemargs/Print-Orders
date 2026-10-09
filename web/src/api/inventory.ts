import { apiFetch } from './http'
import type { InventoryAdjustmentRecord, InventoryItemRecord } from './types'

export type InventorySummary = {
  active_items: number
  low_stock: number
  out_of_stock: number
  stock_value: number
  stores: { location_id: string; store: string; active_items: number; low_stock: number; out_of_stock: number }[]
}

export type InventoryFilters = {
  view?:string;
  search?: string
  location_id?: string
  category?: string
  low_stock?: boolean
  include_inactive?: boolean
  limit?: number
  offset?: number
}

export type InventoryItemInput = {
  location_id: string
  catalog_product_id: string | null
  name: string
  sku: string
  category: string
  unit: string
  quantity: number
  reorder_point: number
  target_stock: number
  cost_per_unit: number
  vendor: string
  vendor_sku: string
  notes: string
  active: boolean
}

function qs(filters: InventoryFilters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key,value]) => {
    if (value !== undefined && value !== '' && value !== false) params.set(key,String(value))
  })
  return params.toString()
}

export const listInventory = (filters: InventoryFilters = {}) =>
  apiFetch<{items:InventoryItemRecord[];total:number}>(`/api/inventory?${qs(filters)}`)

export const getInventorySummary = () => apiFetch<InventorySummary>('/api/inventory/summary')

export const createInventoryItem = (input: InventoryItemInput) =>
  apiFetch<InventoryItemRecord>('/api/inventory',{method:'POST',body:JSON.stringify(input)})

export const updateInventoryItem = (id:string,input:InventoryItemInput&{version:number}) =>
  apiFetch<InventoryItemRecord>(`/api/inventory/${id}`,{method:'PATCH',body:JSON.stringify(input)})

export const adjustInventoryItem = (
  item:InventoryItemRecord,
  mode:'add'|'remove'|'set',
  quantity:number,
  reason:'Received'|'Used'|'Count Correction'|'Waste'|'Other',
  notes=''
) => apiFetch<InventoryItemRecord>(`/api/inventory/${item.id}/adjust`,{
  method:'POST',
  body:JSON.stringify({version:item.version,mode,quantity,reason,notes}),
})

export const getInventoryHistory = (id:string) =>
  apiFetch<{adjustments:InventoryAdjustmentRecord[]}>(`/api/inventory/${id}/history`)
