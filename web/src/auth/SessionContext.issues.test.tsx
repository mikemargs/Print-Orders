import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import { SessionProvider, useSession } from './SessionContext'
import { apiFetch } from '../api/http'
import { issueSession } from '../features/issues/testFixtures'
vi.mock('../api/http',async original=>({...await original<typeof import('../api/http')>(),apiFetch:vi.fn()}))
vi.mock('../offline/db',()=>({cacheSessionInfo:vi.fn(),cachedSessionInfo:vi.fn(),clearOfflineCache:vi.fn(),clearPendingLogout:vi.fn(),pendingLogoutCsrf:vi.fn(),setPendingLogoutCsrf:vi.fn()}))
function Probe(){const s=useSession();return <><span>{s.loading?'Loading':s.session?.employee.name||'Signed out'}</span><button onClick={()=>void s.logout()}>Logout</button><button onClick={()=>s.setSession({...issueSession,employee:{...issueSession.employee,id:'second',name:'Second'}})}>Change employee</button></>}
function setup(){vi.mocked(apiFetch).mockResolvedValue(issueSession);const client=new QueryClient();render(<QueryClientProvider client={client}><SessionProvider><Probe/></SessionProvider></QueryClientProvider>);return client}
it('clears case queries at logout',async()=>{const client=setup();await screen.findByText('Nick');client.setQueryData(['issues','co','e','l','secret'],{summary:'private'});fireEvent.click(screen.getByText('Logout'));await screen.findByText('Signed out');await waitFor(()=>expect(client.getQueryData(['issues','co','e','l','secret'])).toBeUndefined())})
it('clears case queries before switching identity',async()=>{const client=setup();await screen.findByText('Nick');client.setQueryData(['issues','co','e','l','secret'],{summary:'private'});fireEvent.click(screen.getByText('Change employee'));await screen.findByText('Second');expect(client.getQueryData(['issues','co','e','l','secret'])).toBeUndefined()})
