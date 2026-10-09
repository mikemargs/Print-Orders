import { apiFetch } from './http'
import type { MailboxRecord } from './types'

export type MailboxSummary = {
  active: number
  overdue: number
  due_30: number
  missing_compliance: number
  blocked: number
}

export type MailboxFilters = {
  view?:string;
  search?: string
  location_id?: string
  status?: string
  customer_id?: string
  missing_compliance?: boolean
  overdue_only?: boolean
  limit?: number
  offset?: number
}

export type MailboxInput = {
  location_id: string
  customer_id: string
  mailbox_number: string
  status: string
  renewal_date: string | null
  balance_due: number
  primary_id_on_file: boolean
  secondary_id_on_file: boolean
  form_1583_complete: boolean
  msa_complete: boolean
  phone_verified: boolean
  forwarding_status: string
  forwarding_address: string
  notes: string
}

function qs(filters: MailboxFilters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key,value]) => {
    if (value !== undefined && value !== '' && value !== false) params.set(key,String(value))
  })
  return params.toString()
}

export const listMailboxes = (filters: MailboxFilters = {}) =>
  apiFetch<{ mailboxes: MailboxRecord[]; total: number }>(`/api/mailboxes?${qs(filters)}`)

export const getMailboxSummary = () => apiFetch<MailboxSummary>('/api/mailboxes/summary')

export const getMailboxOptions = () =>
  apiFetch<{ customers: { id: string; company: string; first_name: string; last_name: string; phone: string; email: string }[] }>('/api/mailboxes/options')

export const createMailbox = (input: MailboxInput) =>
  apiFetch<MailboxRecord>('/api/mailboxes',{method:'POST',body:JSON.stringify(input)})

export const updateMailbox = (id: string, input: MailboxInput & {version:number}) =>
  apiFetch<MailboxRecord>(`/api/mailboxes/${id}`,{method:'PATCH',body:JSON.stringify(input)})
