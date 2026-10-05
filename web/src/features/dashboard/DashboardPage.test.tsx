import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from './DashboardPage'
import { apiFetch } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheOrders, cachedOrders } from '../../offline/db'

vi.mock('../../api/http', () => ({ apiFetch: vi.fn() }))
vi.mock('../../auth/SessionContext', () => ({ useSession: vi.fn() }))
vi.mock('../../offline/OnlineState', () => ({ useOnline: vi.fn() }))
vi.mock('../../offline/db', () => ({ cacheOrders: vi.fn(), cachedOrders: vi.fn() }))

afterEach(() => vi.clearAllMocks())

const baseOrder = {
  version: 1,
  customer_id: 'c1',
  received_date: '2026-10-01',
  due_date: '2026-10-10',
  assigned_to: '',
  delivery_method: 'Pickup',
  po_number: '',
  artwork_path: '',
  production_notes: '',
  customer_notes: '',
  tax_rate: 0,
  deposit: 0,
  discount: 0,
  discount_mode: 'amount' as const,
  discount_percent: 0,
  subtotal: 25,
  total: 25,
  balance: 25,
  items: [],
  updated_at: '2026-10-05T12:00:00Z',
  updated_by: 'e1',
  is_deleted: false,
}

describe('Main Dashboard', () => {
  it('shows pending orders from all locations and excludes closed orders', async () => {
    vi.mocked(useSession).mockReturnValue({
      session: {
        csrf_token: 'csrf',
        company: { id: 'company', name: 'Print Co', code: 'PRINT' },
        employee: { id: 'e1', name: 'Alex', role: 'admin', location_ids: ['s1', 's2'], active: true },
        location: { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
        locations: [
          { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
          { id: 's2', name: 'Selden', store_number: '5345', timezone: 'America/New_York', active: true },
        ],
      },
      loading: false,
      refresh: vi.fn(),
      setSession: vi.fn(),
      switchLocation: vi.fn(),
      logout: vi.fn(),
    })
    vi.mocked(useOnline).mockReturnValue({ online: true, lastSyncAt: '' })
    vi.mocked(cachedOrders).mockResolvedValue([])
    vi.mocked(cacheOrders).mockResolvedValue(undefined)
    vi.mocked(apiFetch).mockResolvedValue({
      orders: [
        { ...baseOrder, id: 'o1', location_id: 's1', order_number: 'WO-5127-1', status: 'In Production', priority: 'Rush', description: 'Sayville poster' },
        { ...baseOrder, id: 'o2', location_id: 's2', order_number: 'WO-5345-1', status: 'Ready for Pickup', priority: 'Normal', description: 'Selden banner' },
        { ...baseOrder, id: 'o3', location_id: 's2', order_number: 'WO-5345-2', status: 'Completed', priority: 'Normal', description: 'Finished job' },
      ],
    })

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('WO-5127-1')).toBeInTheDocument()
    expect(screen.getByText('WO-5345-1')).toBeInTheDocument()
    expect(screen.queryByText('WO-5345-2')).not.toBeInTheDocument()
    expect(screen.getAllByText('Sayville #5127').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Selden #5345').length).toBeGreaterThan(0)
    expect(screen.getByText('2 total')).toBeInTheDocument()
  })
})
