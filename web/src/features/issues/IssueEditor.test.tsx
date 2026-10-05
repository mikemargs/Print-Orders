import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { IssueEditor } from './IssueEditor'
import { apiFetch, ApiError } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { issueFixture, issueSession } from './testFixtures'
vi.mock('../../api/http',async importOriginal=>({...await importOriginal<typeof import('../../api/http')>(),apiFetch:vi.fn()}))
vi.mock('../../auth/SessionContext',()=>({useSession:vi.fn()}))
vi.mock('../../offline/OnlineState',()=>({useOnline:vi.fn()}))
beforeEach(()=>{
 vi.mocked(useSession).mockReturnValue({session:issueSession,loading:false,refresh:vi.fn(),setSession:vi.fn(),switchLocation:vi.fn(),logout:vi.fn()})
 vi.mocked(useOnline).mockReturnValue({online:true,lastSyncAt:''})
 vi.mocked(apiFetch).mockImplementation(async (path,opts)=>{
  if(path.includes('/options'))return {employees:[issueSession.employee]}
  if(path.includes('/customers'))return {customers:[issueFixture.customer]}
  if(path.includes('/orders'))return {orders:[]}
  if(path.includes('/activities'))return opts?.method==='POST'?{id:'act'}:{activities:[],total:0}
  return issueFixture
 })
})
function mount(path='/issues/i'){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[path]}><Routes><Route path='/issues/new' element={<IssueEditor/>}/><Route path='/issues/:id' element={<IssueEditor/>}/></Routes></MemoryRouter></QueryClientProvider>)}
it('creates a case using selected customer and active store',async()=>{
 mount('/issues/new');await screen.findByRole('option',{name:'Test customer'})
 fireEvent.change(screen.getByLabelText('Customer'),{target:{value:'c'}})
 fireEvent.change(screen.getByLabelText('Case title'),{target:{value:'New complaint'}})
 fireEvent.change(screen.getByLabelText('Issue description'),{target:{value:'Details'}})
 fireEvent.click(screen.getByRole('button',{name:'Save case'}))
 await waitFor(()=>expect(apiFetch).toHaveBeenCalledWith('/api/issues',expect.objectContaining({method:'POST',body:expect.stringContaining('New complaint')})))
})
it('logs a manual communication and resolves then reopens',async()=>{
 mount();await screen.findByDisplayValue('Wrong package')
 fireEvent.change(screen.getByLabelText('Communication summary'),{target:{value:'Customer called'}})
 fireEvent.click(screen.getByRole('button',{name:'Log communication'}))
 await waitFor(()=>expect(apiFetch).toHaveBeenCalledWith('/api/issues/i/activities',expect.objectContaining({method:'POST',body:expect.stringContaining('Customer called')})))
 fireEvent.change(screen.getByLabelText('Resolution summary'),{target:{value:'Replacement provided'}})
 fireEvent.click(screen.getByRole('button',{name:'Resolve case'}))
 await waitFor(()=>expect(apiFetch).toHaveBeenCalledWith('/api/issues/i',expect.objectContaining({method:'PATCH',body:expect.stringContaining('Resolved')})))
})
it('keeps unsaved text on a version conflict and offers review',async()=>{
 const original=vi.mocked(apiFetch).getMockImplementation()!
 vi.mocked(apiFetch).mockImplementation((path,opts)=>opts?.method==='PATCH'?Promise.reject(new ApiError('Changed',409,{...issueFixture,version:2,title:'Server title'})):original(path,opts))
 mount();await screen.findByDisplayValue('Wrong package')
 fireEvent.change(screen.getByLabelText('Case title'),{target:{value:'My unsaved title'}})
 fireEvent.click(screen.getByRole('button',{name:'Save case'}))
 expect(await screen.findByText(/Review the current case/)).toBeVisible()
 expect(screen.getByDisplayValue('My unsaved title')).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'Load current case'}));expect(screen.getByDisplayValue('Server title')).toBeVisible()
})
it('disables changes for a different active store',async()=>{
 vi.mocked(useSession).mockReturnValue({session:{...issueSession,employee:{...issueSession.employee,role:'employee'},location:issueSession.locations[1]},loading:false,refresh:vi.fn(),setSession:vi.fn(),switchLocation:vi.fn(),logout:vi.fn()})
 mount();await screen.findByDisplayValue('Wrong package');expect(screen.getByRole('button',{name:'Save case'})).toBeDisabled();expect(screen.getByRole('button',{name:'Log communication'})).toBeDisabled()
})
it('shows logged text literally in history',async()=>{
 const original=vi.mocked(apiFetch).getMockImplementation()!
 vi.mocked(apiFetch).mockImplementation((path,opts)=>path.includes('/activities')?Promise.resolve({activities:[{id:'act',activity_type:'communication',channel:'email',occurred_at:'2026-10-05T14:00:00Z',recorded_at:'2026-10-05T14:01:00Z',author_name:'Nick',summary:'<script>literal</script>',changed_fields:{}}],total:1}):original(path,opts))
 mount();expect(await screen.findByText('<script>literal</script>')).toBeVisible()
})
it('loads customer choices within the customer API page limit, including later pages',async()=>{
 const original=vi.mocked(apiFetch).getMockImplementation()!
 vi.mocked(apiFetch).mockImplementation((path,opts)=>{
  if(path.startsWith('/api/customers')){
   const url=new URL(path,'http://localhost');const limit=Number(url.searchParams.get('limit'));const offset=Number(url.searchParams.get('offset'))
   if(limit>200)return Promise.reject(new ApiError('Limit must be at most 200',422))
   return Promise.resolve({customers:offset===0?Array.from({length:200},(_,n)=>({...issueFixture.customer,id:`c${n}`,company:`Customer ${n}`})):[{...issueFixture.customer,id:'last',company:'Last customer'}]})
  }
  return original(path,opts)
 })
 mount('/issues/new');expect(await screen.findByRole('option',{name:'Last customer'})).toBeInTheDocument()
})
