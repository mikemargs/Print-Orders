import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SessionProvider } from './SessionContext'

afterEach(() => vi.restoreAllMocks())

describe('LoginPage', () => {
  it('moves from company credentials to employee/store selection without exposing a bearer token', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const path = String(input)
      if (path.endsWith('/api/web/session')) return new Response(JSON.stringify({ detail: 'expired' }), { status: 401, headers: { 'content-type': 'application/json' } })
      return new Response(JSON.stringify({ company:{id:'c',name:'Print Co',code:'PRINT'}, locations:[{id:'l',name:'Sayville',store_number:'5127',timezone:'America/New_York',active:true}], employees:[{id:'e',name:'Alex',role:'employee',location_ids:['l'],active:true}] }), { status: 200, headers: { 'content-type': 'application/json' } })
    })
    render(<QueryClientProvider client={new QueryClient()}><SessionProvider><LoginPage /></SessionProvider></QueryClientProvider>)
    fireEvent.change(screen.getByLabelText('Company code'), { target: { value: 'PRINT' } })
    fireEvent.change(screen.getByLabelText('Company password'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByText('Print Co')).toBeInTheDocument()
    expect(screen.getByLabelText('Store')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Bearer')
  })
})
