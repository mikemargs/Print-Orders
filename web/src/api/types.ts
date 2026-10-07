export type Role = 'employee' | 'supervisor' | 'admin'

export interface Company { id: string; name: string; code: string }
export interface Location { id: string; name: string; store_number: string; timezone: string; active: boolean }
export interface Employee { id: string; name: string; role: Role; location_ids: string[]; active: boolean; auth_version?: number }
export interface SessionInfo { csrf_token: string; company: Company; employee: Employee; location: Location; locations: Location[] }
export interface CompanyStage { company: Company; locations: Location[]; employees: Employee[] }

export interface Customer {
  id: string; version: number; is_deleted: boolean; company: string; first_name: string; last_name: string;
  phone: string; email: string; address1: string; address2: string; city: string; state: string;
  postal_code: string; tax_exempt: boolean; notes: string; updated_at: string; updated_by: string
}
export interface LineItem { item_name?: string; description?: string; quantity: number; unit_price: number; [key: string]: unknown }
export interface WorkOrder {
  id: string; version: number; customer_id: string; location_id: string; order_number: string; status: string; priority: string;
  received_date: string; due_date: string; assigned_to: string; delivery_method: string; po_number: string; description: string;
  artwork_path: string; production_notes: string; customer_notes: string; tax_rate: number; deposit: number; discount: number;
  discount_mode: 'amount' | 'percent'; discount_percent: number; subtotal: number; total: number; balance: number;
  items: LineItem[]; updated_at: string; updated_by: string; is_deleted: boolean; has_artwork?: boolean
}
export interface Attachment { id: string; order_id: string; object_key: string; original_filename: string; mime_type: string; size_bytes: number; uploaded_by: string; created_at: string; checksum: string; active: boolean; deleted?: boolean }


export interface OperationalTask {
  id: string; location_id: string; title: string; description: string;
  status: 'Open' | 'In Progress' | 'Waiting' | 'Completed' | 'Cancelled';
  priority: 'Low' | 'Normal' | 'High' | 'Urgent'; due_date: string | null;
  assigned_employee_id: string | null; customer_id: string | null; work_order_id: string | null;
  customer_issue_id: string | null; version: number; created_by: string; updated_by: string;
  created_at: string; updated_at: string; completed_at: string | null;
  store?: { id: string; name: string; store_number: string; timezone?: string } | null;
  assignee?: { id: string; name: string } | null;
  customer?: { id: string; company: string; first_name: string; last_name: string } | null;
  order_number?: string | null; issue_reference?: string | null;
}
