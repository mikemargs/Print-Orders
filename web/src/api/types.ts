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


export interface MailboxRecord {
  id: string; location_id: string; customer_id: string; mailbox_number: string;
  status: 'Active' | 'Blocked' | 'Closing' | 'Closed'; renewal_date: string | null;
  balance_due: number; primary_id_on_file: boolean; secondary_id_on_file: boolean;
  form_1583_complete: boolean; msa_complete: boolean; phone_verified: boolean;
  forwarding_status: 'None' | 'Scheduled' | 'Active'; forwarding_address: string; notes: string;
  version: number; created_by: string; updated_by: string; created_at: string; updated_at: string;
  closed_at: string | null; days_overdue: number; compliance_complete: boolean; missing_compliance: string[];
  store: { id: string; name: string; store_number: string; timezone: string } | null;
  customer: Pick<Customer,'id'|'company'|'first_name'|'last_name'|'phone'|'email'> | null;
}


export interface ShippingCaseRecord {
  id: string; location_id: string; customer_id: string; customer_issue_id: string | null;
  tracking_number: string; carrier: string; service_level: string;
  case_type: 'GSR' | 'Late Delivery' | 'Lost Package' | 'Damage Claim' | 'Shipping Claim' | 'Address Correction' | 'Other';
  status: 'Open' | 'Submitted' | 'Awaiting Carrier' | 'Awaiting Customer' | 'Approved' | 'Denied' | 'Refunded' | 'Resolved';
  ship_date: string | null; promised_date: string | null; delivered_date: string | null;
  carrier_reference: string; amount_requested: number; amount_approved: number;
  next_action: string; follow_up_date: string | null; notes: string; version: number;
  created_by: string; updated_by: string; created_at: string; updated_at: string; resolved_at: string | null;
  store: { id: string; name: string; store_number: string; timezone: string } | null;
  customer: Pick<Customer,'id'|'company'|'first_name'|'last_name'|'phone'|'email'> | null;
  issue_reference: string | null; issue_title: string | null;
}


export interface OperationsChecklistCompletion {
  id: string; status: 'Completed' | 'Skipped'; notes: string; checklist_date: string;
  completed_by: string; completed_by_name: string; completed_at: string; version: number;
}

export interface OperationsChecklistItem {
  id: string; location_id: string; title: string; description: string;
  category: 'Opening' | 'Closing' | 'Cleaning' | 'Equipment' | 'Deposit' | 'Supplies' | 'Safety' | 'Daily' | 'Other';
  active_days: number[]; required: boolean; active: boolean; sort_order: number; version: number;
  created_by: string; updated_by: string; created_at: string; updated_at: string;
  store: { id: string; name: string; store_number: string; timezone: string } | null;
  completion: OperationsChecklistCompletion | null;
}


export interface InventoryItemRecord {
  id: string; location_id: string; name: string; sku: string; category: string; unit: string;
  quantity: number; reorder_point: number; target_stock: number; cost_per_unit: number;
  vendor: string; vendor_sku: string; notes: string; active: boolean; version: number;
  created_by: string; updated_by: string; created_at: string; updated_at: string;
  low_stock: boolean; out_of_stock: boolean; stock_value: number;
  store: { id: string; name: string; store_number: string } | null;
}

export interface InventoryAdjustmentRecord {
  id: string; item_id: string; location_id: string; change_amount: number; resulting_quantity: number;
  reason: 'Received' | 'Used' | 'Count Correction' | 'Waste' | 'Other'; notes: string;
  adjusted_by: string; adjusted_by_name: string; created_at: string;
}

export interface EquipmentAssetRecord {
  id: string; location_id: string; name: string; category: string; asset_tag: string;
  manufacturer: string; model: string; serial_number: string;
  status: 'Operational' | 'Needs Attention' | 'Out of Service' | 'Retired';
  purchase_date: string | null; warranty_expiration: string | null; vendor: string;
  service_provider: string; next_service_date: string | null; notes: string; active: boolean;
  version: number; created_by: string; updated_by: string; created_at: string; updated_at: string;
  service_overdue: boolean; service_due_30: boolean;
  store: { id: string; name: string; store_number: string; timezone: string } | null;
}

export interface EquipmentServiceEventRecord {
  id: string; equipment_id: string; location_id: string; event_date: string;
  event_type: 'Maintenance' | 'Repair' | 'Inspection' | 'Service Call' | 'Issue Reported' | 'Other';
  summary: string; provider: string; cost: number; recorded_by: string; recorded_by_name: string; created_at: string;
}
