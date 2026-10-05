import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { IssuesPage } from './IssuesPage'
import { apiFetch } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { issueFixture, issueSession } from './testFixtures'
vi.mock('../../api/http',()=>({apiFetch:vi.fn()}))
vi.mock('../../auth/SessionContext',()=>({useSession:vi.fn()}))
vi.mock('../../offline/OnlineState',()=>({useOnline:vi.fn()}))
beforeEach(()=>{
 vi.mocked(useSession).mockReturnValue({session:issueSession,loading:false,refresh:vi.fn(),setSession:vi.fn(),switchLocation:vi.fn(),logout:vi.fn()})
 vi.mocked(useOnline).mockReturnValue({online:true,lastSyncAt:''})
 vi.mocked(apiFetch).mockImplementation(async path=>path.includes('/summary')?{open:271,overdue:3,high_priority:4,assigned_to_me:2}:path.includes('/options')?{employees:[issueSession.employee]}:{issues:[issueFixture],total:271})
})
function mount(){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><IssuesPage/></MemoryRouter></QueryClientProvider>)}
it('shows full summary, case store, filters and pagination',async()=>{
 mount();expect(await screen.findByText('Wrong package')).toBeVisible();expect(screen.getByText('271 matching cases')).toBeVisible()
 fireEvent.change(screen.getByLabelText('Filter by store'),{target:{value:'l2'}})
 await waitFor(()=>expect(apiFetch).toHaveBeenCalledWith(expect.stringContaining('location_id=l2')))
 fireEvent.click(await screen.findByRole('button',{name:'Next page'}));await waitFor(()=>expect(apiFetch).toHaveBeenCalledWith(expect.stringContaining('offset=50')))
})
it('shows an error with retry instead of an empty case list',async()=>{
 vi.mocked(apiFetch).mockRejectedValue(new Error('Server unavailable'));mount()
 expect(await screen.findAllByText(/Server unavailable/,{}, {timeout:3000})).not.toHaveLength(0)
 expect(screen.queryByText('No customer issues match these filters.')).not.toBeInTheDocument()
})
it('requires connection and hides new case control offline',()=>{
 vi.mocked(useOnline).mockReturnValue({online:false,lastSyncAt:''});mount()
 expect(screen.getByText(/Customer issues require an online connection/)).toBeVisible()
 expect(screen.queryByRole('link',{name:'New case'})).not.toBeInTheDocument()
})
