import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { OrdersPage } from './OrdersPage'
import { apiFetch } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheOrders, cachedOrders } from '../../offline/db'

vi.mock('../../api/http', () => ({ apiFetch: vi.fn() }))
vi.mock('../../auth/SessionContext', () => ({ useSession: vi.fn() }))
vi.mock('../../offline/OnlineState', () => ({ useOnline: vi.fn() }))
vi.mock('../../offline/db', () => ({ cacheOrders: vi.fn(), cachedOrders: vi.fn() }))

afterEach(() => vi.clearAllMocks())

const session = {
  csrf_token: 'csrf',
  company: { id: 'company', name: 'Print Co', code: 'PRINT' },
  employee: { id: 'e1', name: 'Alex', role: 'admin' as const, location_ids: ['s1'], active: true },
  location: { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
  locations: [{ id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true }],
}

const baseOrder = {
  version: 1,
  customer_id: 'c1',
  location_id: 's1',
  status: 'In Production',
  priority: 'Normal',
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

describe('Work Orders artwork status', () => {
  it('shows Artwork between Description and Total with per-order upload status', async () => {
    vi.mocked(useSession).mockReturnValue({
      session,
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
        { ...baseOrder, id: 'o1', order_number: 'WO-1', description: 'Banner', has_artwork: true },
        { ...baseOrder, id: 'o2', order_number: 'WO-2', description: 'Poster', has_artwork: false },
      ],
    })

    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <OrdersPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('WO-1')).toBeInTheDocument()
    const headers = screen.getAllByRole('columnheader').map(header => header.textContent)
    expect(headers).toEqual(['Order', 'Status', 'Priority', 'Due', 'Description', 'Artwork', 'Total'])
    expect(screen.getByText('Uploaded')).toBeInTheDocument()
    expect(screen.getByText('Not Uploaded')).toBeInTheDocument()
  })
})
