import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from './AppShell'
import { useSession } from '../auth/SessionContext'
import { useOnline } from '../offline/OnlineState'

vi.mock('../auth/SessionContext', () => ({ useSession: vi.fn() }))
vi.mock('../offline/OnlineState', () => ({ useOnline: vi.fn() }))

afterEach(() => vi.clearAllMocks())

describe('AppShell store switcher', () => {
  it('switches the active store without signing in again', async () => {
    const switchLocation = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useSession).mockReturnValue({
      session: {
        csrf_token: 'csrf',
        company: { id: 'c', name: 'Print Co', code: 'PRINT' },
        employee: {
          id: 'e',
          name: 'Alex',
          role: 'employee',
          location_ids: ['l1', 'l2'],
          active: true,
        },
        location: { id: 'l1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
        locations: [
          { id: 'l1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
          { id: 'l2', name: 'Selden', store_number: '5345', timezone: 'America/New_York', active: true },
        ],
      },
      loading: false,
      refresh: vi.fn(),
      setSession: vi.fn(),
      switchLocation,
      logout: vi.fn(),
    })
    vi.mocked(useOnline).mockReturnValue({ online: true, lastSyncAt: '' })

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AppShell />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    fireEvent.change(screen.getByLabelText('Active store'), { target: { value: 'l2' } })
    await waitFor(() => expect(switchLocation).toHaveBeenCalledWith('l2'))
  })

  it('disables store switching while offline', () => {
    vi.mocked(useSession).mockReturnValue({
      session: {
        csrf_token: 'csrf',
        company: { id: 'c', name: 'Print Co', code: 'PRINT' },
        employee: {
          id: 'e',
          name: 'Alex',
          role: 'employee',
          location_ids: ['l1', 'l2'],
          active: true,
        },
        location: { id: 'l1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
        locations: [
          { id: 'l1', name: 'Sayville', store_number: '5127', timezone: 'America/New_York', active: true },
          { id: 'l2', name: 'Selden', store_number: '5345', timezone: 'America/New_York', active: true },
        ],
      },
      loading: false,
      refresh: vi.fn(),
      setSession: vi.fn(),
      switchLocation: vi.fn(),
      logout: vi.fn(),
    })
    vi.mocked(useOnline).mockReturnValue({ online: false, lastSyncAt: '' })

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AppShell />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByLabelText('Active store')).toBeDisabled()
    expect(screen.getByText(/Store switching is available again/)).toBeInTheDocument()
  })
})
