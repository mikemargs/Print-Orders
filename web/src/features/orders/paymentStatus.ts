import type { WorkOrder } from '../../api/types'

export function paymentStatus(order: Pick<WorkOrder, 'paid_in_full'|'total'|'deposit'|'balance'>): string {
  if (order.paid_in_full || (order.total > 0 && order.balance <= 0)) return 'Paid in full'
  if (order.total <= 0) return 'No balance due'
  return order.deposit > 0 ? 'Deposit received' : 'Unpaid'
}
