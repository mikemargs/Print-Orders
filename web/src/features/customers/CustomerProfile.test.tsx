import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/http'
import { listIssues } from '../../api/issues'
import { listTasks } from '../../api/tasks'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cacheOrders } from '../../offline/db'
import { CustomerProfile } from './CustomerProfile'

vi.mock('../../api/http', () => ({ apiFetch: vi.fn() }))
vi.mock('../../api/issues', () => ({ listIssues: vi.fn() }))
vi.mock('../../api/tasks', () => ({ listTasks: vi.fn() }))
vi.mock('../../auth/SessionContext', () => ({ useSession: vi.fn() }))
vi.mock('../../offline/OnlineState', () => ({ useOnline: vi.fn() }))
vi.mock('../../offline/db', () => ({
  cacheCustomers: vi.fn(),
  cacheOrders: vi.fn(),
  cachedCustomer: vi.fn(),
  cachedOrders: vi.fn(),
}))

afterEach(() => vi.clearAllMocks())

describe('CustomerProfile', () => {
  it('shows linked operational history and customer-scoped actions', async () => {
    vi.mocked(useOnline).mockReturnValue({ online: true, lastSyncAt: '' })
    vi.mocked(useSession).mockReturnValue({
      session: {
        csrf_token: 'csrf',
        company: { id: 'co', name: 'Print Co', code: 'PRINT' },
        employee: { id: 'e1', name: 'Alex', role: 'admin', location_ids: ['s1'], active: true },
        location: { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
        locations: [{ id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true }],
      },
      loading: false,
      refresh: vi.fn(),
      setSession: vi.fn(),
      switchLocation: vi.fn(),
      logout: vi.fn(),
    })
    vi.mocked(cacheCustomers).mockResolvedValue(undefined)
    vi.mocked(cacheOrders).mockResolvedValue(undefined)
    vi.mocked(apiFetch).mockImplementation(async (url: string) => {
      if (url === '/api/customers/c1') return {
        id: 'c1', version: 1, is_deleted: false, company: 'Acme Landscaping', first_name: 'Sam', last_name: 'Lee',
        phone: '631-555-0100', email: 'sam@example.com', address1: '1 Main St', address2: '', city: 'Sayville',
        state: 'NY', postal_code: '11782', tax_exempt: false, notes: 'Prefers email',
        updated_at: '2026-10-07T12:00:00Z', updated_by: 'e1',
      }
      if (url.startsWith('/api/orders?customer_id=c1')) return { orders: [{
        id: 'o1', version: 1, customer_id: 'c1', location_id: 's1', order_number: 'WO-1', status: 'In Production',
        priority: 'Rush', received_date: '2026-10-01', due_date: '2026-10-08', assigned_to: '', delivery_method: 'Pickup',
        po_number: '', description: 'Yard signs', artwork_path: '', production_notes: '', customer_notes: '', tax_rate: 8.625,
        deposit: 0, discount: 0, discount_mode: 'amount', discount_percent: 0, subtotal: 100, total: 108.63,
        balance: 108.63, items: [], updated_at: '2026-10-07T12:00:00Z', updated_by: 'e1', is_deleted: false,
      }] }
      throw new Error('Unexpected URL: ' + url)
    })
    vi.mocked(listIssues).mockResolvedValue({ total: 1, issues: [{
      id: 'i1', reference: 'CI-1', version: 1, customer_id: 'c1', location_id: 's1', title: 'Delivery concern',
      description: 'Details', category: 'Customer Service', priority: 'High', status: 'Open', assigned_employee_id: null,
      work_order_id: null, next_action: 'Call customer', follow_up_date: '2026-10-08', resolution_summary: '',
      created_at: '2026-10-07T12:00:00Z', updated_at: '2026-10-07T12:00:00Z', resolved_at: null,
      created_by: 'e1', updated_by: 'e1', customer: null,
      store: { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York' },
      assignee: null, order_number: null,
    }] })
    vi.mocked(listTasks).mockResolvedValue({ total: 1, tasks: [{
      id: 't1', location_id: 's1', title: 'Confirm artwork', description: '', status: 'Open', priority: 'High',
      due_date: '2026-10-08', assigned_employee_id: 'e1', customer_id: 'c1', work_order_id: 'o1',
      customer_issue_id: null, version: 1, created_by: 'e1', updated_by: 'e1',
      created_at: '2026-10-07T12:00:00Z', updated_at: '2026-10-07T12:00:00Z', completed_at: null,
      store: { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York' },
      assignee: { id: 'e1', name: 'Alex' }, customer: null, order_number: 'WO-1', issue_reference: null,
    }] })

    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/customers/c1']}>
          <Routes><Route path="/customers/:id" element={<CustomerProfile/>}/></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('heading', { name: 'Acme Landscaping' })).toBeInTheDocument()
    expect(screen.getByText('Yard signs')).toBeInTheDocument()
    expect(screen.getByText('Delivery concern')).toBeInTheDocument()
    expect(screen.getByText('Confirm artwork')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Edit Customer' })).toHaveAttribute('href', '/customers/c1/edit')
    expect(screen.getByRole('link', { name: 'New Work Order' })).toHaveAttribute('href', '/orders/new?customer_id=c1')
    expect(screen.getByRole('link', { name: 'New Customer Issue' })).toHaveAttribute('href', '/issues/new?customer_id=c1')
    expect(screen.getByRole('link', { name: 'New Task' })).toHaveAttribute('href', '/tasks?customer_id=c1&new=1')
  })
})
