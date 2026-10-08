import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import { SessionProvider, useSession } from './SessionContext'
import { clearOfflineCache, setPendingLogoutCsrf } from '../offline/db'
import { apiFetch, getCsrfToken } from '../api/http'
import { issueSession } from '../features/issues/testFixtures'
vi.mock('../api/http',async original=>({...await original<typeof import('../api/http')>(),apiFetch:vi.fn()}))
vi.mock('../offline/db',()=>({cacheSessionInfo:vi.fn(),cachedSessionInfo:vi.fn(),clearOfflineCache:vi.fn(),clearPendingLogout:vi.fn(),pendingLogoutCsrf:vi.fn(),setPendingLogoutCsrf:vi.fn()}))
function Probe(){const s=useSession();return <><span>{s.loading?'Loading':s.session?.employee.name||'Signed out'}</span><button onClick={()=>void s.switchLocation("other").catch(()=>{})}>Switch</button><button onClick={()=>void s.refresh()}>Refresh</button><button onClick={()=>void s.logout()}>Logout</button><button onClick={()=>s.setSession({...issueSession,employee:{...issueSession.employee,id:'second',name:'Second'}})}>Change employee</button></>}
function setup(){vi.mocked(apiFetch).mockResolvedValue(issueSession);const client=new QueryClient();render(<QueryClientProvider client={client}><SessionProvider><Probe/></SessionProvider></QueryClientProvider>);return client}
it('clears case queries at logout',async()=>{const client=setup();await screen.findByText('Nick');client.setQueryData(['issues','co','e','l','secret'],{summary:'private'});fireEvent.click(screen.getByText('Logout'));await screen.findByText('Signed out');await waitFor(()=>expect(client.getQueryData(['issues','co','e','l','secret'])).toBeUndefined())})
it('clears case queries before switching identity',async()=>{const client=setup();await screen.findByText('Nick');client.setQueryData(['issues','co','e','l','secret'],{summary:'private'});fireEvent.click(screen.getByText('Change employee'));await screen.findByText('Second');expect(client.getQueryData(['issues','co','e','l','secret'])).toBeUndefined()})

it('does not restore a session from a refresh that finishes after logout',async()=>{
 setup();await screen.findByText('Nick')
 let resolveRefresh!:(value:typeof issueSession)=>void
 vi.mocked(apiFetch).mockImplementationOnce(()=>new Promise(resolve=>{resolveRefresh=resolve}))
 fireEvent.click(screen.getByText('Refresh'))
 await waitFor(()=>expect(resolveRefresh).toBeDefined())
 fireEvent.click(screen.getByText('Logout'));await screen.findByText('Signed out')
 await act(async()=>resolveRefresh(issueSession))
 expect(screen.getByText('Signed out')).toBeInTheDocument()
})
it('persists offline logout before showing the signed-out screen',async()=>{
 setup();await screen.findByText('Nick')
 const online=vi.spyOn(navigator,'onLine','get').mockReturnValue(false)
 let finishClear!:()=>void
 vi.mocked(clearOfflineCache).mockImplementationOnce(()=>new Promise(resolve=>{finishClear=resolve}))
 fireEvent.click(screen.getByText('Logout'))
 await waitFor(()=>expect(finishClear).toBeDefined())
 expect(screen.queryByText('Signed out')).not.toBeInTheDocument()
 await act(async()=>finishClear())
 await screen.findByText('Signed out')
 expect(setPendingLogoutCsrf).toHaveBeenCalledWith(issueSession.csrf_token)
 online.mockRestore()
})

it('waits for an in-flight store switch before logout and ignores its session',async()=>{
 setup();await screen.findByText('Nick')
 let finishSwitch!:(value:typeof issueSession)=>void
 vi.mocked(apiFetch).mockImplementationOnce(()=>new Promise(resolve=>{finishSwitch=resolve})).mockImplementationOnce(async()=>{expect(getCsrfToken()).toBe('rotated-switch-csrf');return issueSession})
 fireEvent.click(screen.getByText('Switch'))
 await waitFor(()=>expect(finishSwitch).toBeDefined())
 const beforeLogout=vi.mocked(apiFetch).mock.calls.length
 fireEvent.click(screen.getByText('Logout'))
 await act(async()=>{})
 expect(vi.mocked(apiFetch).mock.calls.slice(beforeLogout).some(([url])=>url==='/api/web/auth/logout')).toBe(false)
 await act(async()=>finishSwitch({...issueSession,csrf_token:'rotated-switch-csrf',employee:{...issueSession.employee,name:'Stale switch'}}))
 await screen.findByText('Signed out')
 expect(screen.queryByText('Stale switch')).not.toBeInTheDocument()
})
