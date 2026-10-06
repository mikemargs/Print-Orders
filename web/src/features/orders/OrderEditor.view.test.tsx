import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cacheOrders, cachedCustomers } from '../../offline/db'
import { OrderEditor } from './OrderEditor'

vi.mock('../../api/http', () => ({ apiFetch: vi.fn() }))
vi.mock('../../auth/SessionContext', () => ({ useSession: vi.fn() }))
vi.mock('../../offline/OnlineState', () => ({ useOnline: vi.fn() }))
vi.mock('../../offline/db', () => ({
  cacheCustomers: vi.fn(),
  cacheOrders: vi.fn(),
  cachedCustomers: vi.fn(),
  cachedOrder: vi.fn(),
}))

afterEach(() => vi.clearAllMocks())

const order = {
  id: 'o1',
  version: 1,
  customer_id: 'c1',
  location_id: 's1',
  order_number: 'WO-5127-1001',
  status: 'New',
  priority: 'Normal',
  received_date: '2026-10-06',
  due_date: '2026-10-10',
  assigned_to: 'Alex',
  delivery_method: 'Pickup',
  po_number: '',
  description: 'Original description',
  artwork_path: '',
  production_notes: 'Print carefully',
  customer_notes: '',
  tax_rate: 8.625,
  deposit: 0,
  discount: 0,
  discount_mode: 'amount' as const,
  discount_percent: 0,
  subtotal: 25,
  total: 27.16,
  balance: 27.16,
  items: [{ item_name: 'Poster', quantity: 1, unit_price: 25 }],
  updated_at: '2026-10-06T12:00:00Z',
  updated_by: 'e1',
  is_deleted: false,
}

const customer = {
  id: 'c1',
  version: 1,
  is_deleted: false,
  company: 'Test Customer',
  first_name: '',
  last_name: '',
  phone: '631-555-0100',
  email: 'test@example.com',
  address1: '',
  address2: '',
  city: '',
  state: '',
  postal_code: '',
  tax_exempt: false,
  notes: '',
  updated_at: '2026-10-06T12:00:00Z',
  updated_by: 'e1',
}

describe('OrderEditor saved-order view mode', () => {
  it('opens read-only, allows explicit editing, then returns to read-only after save', async () => {
    vi.mocked(useSession).mockReturnValue({
      session: {
        csrf_token: 'csrf',
        company: { id: 'company', name: 'Print Co', code: 'PRINT' },
        employee: { id: 'e1', name: 'Alex', role: 'admin', location_ids: ['s1'], active: true },
        location: { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
        locations: [
          { id: 's1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
        ],
      },
      loading: false,
      refresh: vi.fn(),
      setSession: vi.fn(),
      switchLocation: vi.fn(),
      logout: vi.fn(),
    })
    vi.mocked(useOnline).mockReturnValue({ online: true, lastSyncAt: '' })
    vi.mocked(cachedCustomers).mockResolvedValue([])
    vi.mocked(cacheCustomers).mockResolvedValue(undefined)
    vi.mocked(cacheOrders).mockResolvedValue(undefined)

    vi.mocked(apiFetch).mockImplementation(async (url: string, options?: RequestInit) => {
      if (url === '/api/customers?limit=200') return { customers: [customer] }
      if (url === '/api/orders/o1' && !options?.method) return order
      if (url === '/api/orders/o1/files') return { files: [] }
      if (url === '/api/orders/o1' && options?.method === 'PATCH') {
        const payload = JSON.parse(String(options.body))
        return { ...order, ...payload, version: 2 }
      }
      throw new Error('Unexpected API call: ' + url)
    })

    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/orders/o1']}>
          <Routes>
            <Route path="/orders/:id" element={<OrderEditor />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('WO-5127-1001')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit Work Order' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Description')).not.toBeInTheDocument()
    expect(screen.getByText('Original description')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Edit Work Order' }))
    const description = screen.getByLabelText('Description')
    fireEvent.change(description, { target: { value: 'Updated description' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save work order' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Edit Work Order' })).toBeInTheDocument())
    expect(screen.queryByLabelText('Description')).not.toBeInTheDocument()
    expect(screen.getByText('Updated description')).toBeInTheDocument()
  })
})
