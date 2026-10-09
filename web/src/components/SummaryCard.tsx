import type { ReactNode } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

export function SummaryCard({ to, children, disabled = false }: {
  to: string; children: ReactNode; disabled?: boolean
}) {
  return disabled
    ? <div className="metric">{children}</div>
    : <Link className="metric metric-link" to={to}>{children}</Link>
}

const viewLabels: Record<string, string> = {
  active: 'Active records', tiered: 'Tiered pricing', manual: 'Manual price', categories: 'Categories',
  pending: 'Pending', rush: 'Rush pending orders', ready: 'Ready for pickup', overdue: 'Overdue',
  due_30: 'Due within 30 days', missing_compliance: 'Missing compliance', open: 'Open records',
  high_priority: 'High / urgent', mine: 'Assigned to me', low: 'Low stock', out: 'Out of stock',
  value: 'Stock value', needs_attention: 'Needs attention', out_of_service: 'Out of service',
  attention: 'Equipment attention', service_overdue: 'Service overdue', gsr: 'GSR pending',
  claims: 'Claims pending', expected: 'Expected checklist items', completed: 'Completed checklist items',
  required_pending: 'Required pending checklist items', sales: 'Orders contributing to sales',
  outstanding: 'Orders with a balance due',
}

export function ViewNotice() {
  const [params] = useSearchParams()
  const { pathname } = useLocation()
  const view = params.get('view')
  if (!view || view === 'all') return null
  const cleared = new URLSearchParams(params)
  cleared.delete('view')
  cleared.delete('offset')
  return <div className="notice" role="status">
    Showing: <strong>{viewLabels[view] ?? view}</strong>.{' '}
    <Link to={`${pathname}?${cleared}`}>Clear summary filter</Link>
  </div>
}

export function useUrlValue(name: string, fallback = ''): [string, (value: string) => void] {
  const [params, setParams] = useSearchParams()
  return [params.get(name) ?? fallback, next => {
    setParams(old => {
      const updated = new URLSearchParams(old)
      updated.set(name, next)
      updated.delete('offset')
      return updated
    }, { replace: true })
  }]
}

export function useUrlFlag(name: string, fallback = false): [boolean, (value: boolean) => void] {
  const [value, setValue] = useUrlValue(name, fallback ? '1' : '0')
  return [value === '1' || value === 'true', next => setValue(next ? '1' : '0')]
}

export function useListView() {
  const [params] = useSearchParams()
  const raw = Number(params.get('offset'))
  const offset = Number.isSafeInteger(raw) ? Math.max(0, raw) : 0
  return { view: params.get('view') ?? '', offset }
}

export function PageNavigation({ total, limit, count, disabled = false }: {
  total?: number; limit: number; count: number; disabled?: boolean
}) {
  const [, setParams] = useSearchParams()
  const { offset } = useListView()
  function change(next: number) {
    setParams(old => {
      const updated = new URLSearchParams(old)
      updated.set('offset', String(next))
      return updated
    })
  }
  return <div className="button-row">
    <button className="secondary" disabled={disabled || offset === 0} onClick={() => change(Math.max(0, offset - limit))}>Previous page</button>
    <span>{total !== undefined ? `${total} matching · ` : ''}Page {Math.floor(offset / limit) + 1}</span>
    <button className="secondary" disabled={disabled || (total !== undefined ? offset + limit >= total : count < limit)} onClick={() => change(offset + limit)}>Next page</button>
  </div>
}
