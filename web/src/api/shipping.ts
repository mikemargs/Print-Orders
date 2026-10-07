import { apiFetch } from './http'
import type { ShippingCaseRecord } from './types'

export const shippingCaseTypes = ['GSR','Late Delivery','Lost Package','Damage Claim','Shipping Claim','Address Correction','Other'] as const
export const shippingStatuses = ['Open','Submitted','Awaiting Carrier','Awaiting Customer','Approved','Denied','Refunded','Resolved'] as const

export type ShippingSummary = {
  open: number
  overdue_followups: number
  gsr_pending: number
  claims_pending: number
  approved: number
}

export type ShippingFilters = {
  search?: string
  location_id?: string
  customer_id?: string
  status?: string
  case_type?: string
  open_only?: boolean
  limit?: number
  offset?: number
}

export type ShippingCaseInput = {
  location_id: string
  customer_id: string
  customer_issue_id: string | null
  tracking_number: string
  carrier: string
  service_level: string
  case_type: string
  status: string
  ship_date: string | null
  promised_date: string | null
  delivered_date: string | null
  carrier_reference: string
  amount_requested: number
  amount_approved: number
  next_action: string
  follow_up_date: string | null
  notes: string
}

function qs(filters: ShippingFilters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key,value]) => {
    if (value !== undefined && value !== '' && value !== false) params.set(key,String(value))
  })
  if (filters.open_only === false) params.set('open_only','false')
  return params.toString()
}

export const listShippingCases = (filters: ShippingFilters = {}) =>
  apiFetch<{ cases: ShippingCaseRecord[]; total: number }>(`/api/shipping-cases?${qs(filters)}`)

export const getShippingSummary = () => apiFetch<ShippingSummary>('/api/shipping-cases/summary')

export const getShippingOptions = () => apiFetch<{
  customers: { id: string; company: string; first_name: string; last_name: string }[]
  issues: { id: string; reference: string; title: string; customer_id: string; location_id: string }[]
}>('/api/shipping-cases/options')

export const createShippingCase = (input: ShippingCaseInput) =>
  apiFetch<ShippingCaseRecord>('/api/shipping-cases',{method:'POST',body:JSON.stringify(input)})

export const updateShippingCase = (id:string,input:ShippingCaseInput&{version:number}) =>
  apiFetch<ShippingCaseRecord>(`/api/shipping-cases/${id}`,{method:'PATCH',body:JSON.stringify(input)})
