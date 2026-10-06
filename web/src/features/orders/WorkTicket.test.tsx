import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cacheOrders } from '../../offline/db'
import { calculateTaxAmount, storeAddressFor, WorkTicket } from './WorkTicket'

vi.mock('../../api/http', () => ({ apiFetch: vi.fn() }))
vi.mock('../../auth/SessionContext', () => ({ useSession: vi.fn() }))
vi.mock('../../offline/OnlineState', () => ({ useOnline: vi.fn() }))
vi.mock('../../offline/db', () => ({
  cacheCustomers: vi.fn(),
  cacheOrders: vi.fn(),
  cachedCustomer: vi.fn(),
  cachedOrder: vi.fn(),
}))

afterEach(() => vi.clearAllMocks())

describe('WorkTicket print sheet', () => {
  it('maps each store number to its printed address', () => {
    expect(storeAddressFor('5127')).toBe('161 North Main St, Sayville, NY 11782')
    expect(storeAddressFor('5345')).toBe('1070 Middle Country Rd, Selden, NY 11784')
    expect(storeAddressFor('3167')).toBe('5507 Nesconset Hwy #10, Mount Sinai, NY 11766')
    expect(storeAddressFor('9999')).toBe('')
  })

  it('calculates tax after the discount', () => {
    expect(calculateTaxAmount(100, 10, 8.625)).toBeCloseTo(7.7625)
  })

  it('prints the new heading, store address, and tax line', async () => {
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
    vi.mocked(cacheOrders).mockResolvedValue(undefined)
    vi.mocked(cacheCustomers).mockResolvedValue(undefined)
    vi.mocked(apiFetch).mockImplementation(async (url: string) => {
      if (url === '/api/orders/o1') {
        return {
          id: 'o1',
          version: 1,
          customer_id: 'c1',
          location_id: 's1',
          order_number: 'WO-5127-TEST',
          status: 'New',
          priority: 'Normal',
          received_date: '2026-10-06',
          due_date: '2026-10-10',
          assigned_to: 'Alex',
          delivery_method: 'Pickup',
          po_number: '',
          description: 'Poster order',
          artwork_path: '',
          production_notes: '',
          customer_notes: '',
          tax_rate: 8.625,
          deposit: 0,
          discount: 10,
          discount_mode: 'amount',
          discount_percent: 0,
          subtotal: 100,
          total: 97.76,
          balance: 97.76,
          items: [{ item_name: 'Poster', quantity: 1, unit_price: 100 }],
          updated_at: '2026-10-06T12:00:00Z',
          updated_by: 'e1',
          is_deleted: false,
        }
      }
      if (url === '/api/customers/c1') {
        return {
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
      }
      throw new Error('Unexpected URL: ' + url)
    })

    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/orders/o1/print']}>
          <Routes>
            <Route path="/orders/:id/print" element={<WorkTicket />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('WO-5127-TEST')).toBeInTheDocument()
    expect(screen.getByText('PRINT ORDER')).toBeInTheDocument()
    expect(screen.getByText('161 North Main St, Sayville, NY 11782')).toBeInTheDocument()
    expect(screen.getByText('Tax (8.625%) $7.76')).toBeInTheDocument()
  })
})
