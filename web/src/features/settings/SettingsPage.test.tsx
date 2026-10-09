import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/http'
import { useOnline } from '../../offline/OnlineState'
import { SettingsPage } from './SettingsPage'

vi.mock('../../api/http',()=>({apiFetch:vi.fn()}))
vi.mock('../../offline/OnlineState',()=>({useOnline:vi.fn()}))
afterEach(()=>vi.clearAllMocks())

it('loads defaults, saves tax changes, and updates defaults used for new orders',async()=>{
  vi.mocked(useOnline).mockReturnValue({online:true,lastSyncAt:''})
  const initial={version:1,default_tax_rate:0,default_order_priority:'Normal',default_delivery_method:'Pickup'}
  vi.mocked(apiFetch).mockResolvedValueOnce(initial).mockResolvedValueOnce({...initial,version:2,default_tax_rate:8.625})
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
  render(<QueryClientProvider client={client}><SettingsPage/></QueryClientProvider>)
  const input=await screen.findByLabelText('Default tax rate (%)')
  fireEvent.change(input,{target:{value:'8.625'}})
  fireEvent.click(screen.getByRole('button',{name:'Save settings'}))
  expect(await screen.findByRole('status')).toHaveTextContent('Settings saved.')
  await waitFor(()=>expect(client.getQueryData(['order-defaults'])).toEqual({...initial,version:2,default_tax_rate:8.625}))
  expect(apiFetch).toHaveBeenLastCalledWith('/api/settings',expect.objectContaining({method:'PATCH',body:JSON.stringify({...initial,default_tax_rate:8.625})}))
})

it('does not allow settings changes offline',()=>{
  vi.mocked(useOnline).mockReturnValue({online:false,lastSyncAt:''})
  render(<QueryClientProvider client={new QueryClient()}><SettingsPage/></QueryClientProvider>)
  expect(screen.getByText('Settings require an internet connection.')).toBeInTheDocument()
  expect(apiFetch).not.toHaveBeenCalled()
})

it('waits for fresh settings before exposing a cached form',async()=>{
  vi.mocked(useOnline).mockReturnValue({online:true,lastSyncAt:''})
  const cached={version:1,default_tax_rate:0,default_order_priority:'Normal',default_delivery_method:'Pickup'}
  let complete!:(value:typeof cached)=>void
  vi.mocked(apiFetch).mockReturnValue(new Promise(resolve=>{complete=resolve}))
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
  client.setQueryData(['settings'],cached)
  render(<QueryClientProvider client={client}><SettingsPage/></QueryClientProvider>)
  expect(screen.queryByLabelText('Default tax rate (%)')).not.toBeInTheDocument()
  await act(async()=>complete({...cached,version:2,default_tax_rate:8.625}))
  expect(await screen.findByLabelText('Default tax rate (%)')).toHaveValue(8.625)
})
