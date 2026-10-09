import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { issueSession } from '../issues/testFixtures'
import { OperationsPage } from './OperationsPage'
vi.mock('../../api/http',()=>({apiFetch:vi.fn()}))
vi.mock('../../auth/SessionContext',()=>({useSession:vi.fn()}))
vi.mock('../../offline/OnlineState',()=>({useOnline:vi.fn()}))
it('filters checklist cards and completes an all-store item using its local date',async()=>{
 vi.mocked(useSession).mockReturnValue({session:issueSession,loading:false,refresh:vi.fn(),setSession:vi.fn(),switchLocation:vi.fn(),logout:vi.fn()})
 vi.mocked(useOnline).mockReturnValue({online:true,lastSyncAt:''})
 const base={description:'',category:'Opening',active_days:[0,1,2,3,4,5,6],active:true,sort_order:0,version:1,created_by:'e',updated_by:'e',created_at:'',updated_at:'',location_id:'l2',checklist_date:'2026-10-10',required:true,store:issueSession.locations[1]}
 const done={id:'done',status:'Completed',notes:'',completed_by:'e',completed_by_name:'Nick',completed_at:'2026-10-10T00:00:00Z',checklist_date:'2026-10-10',version:1}
 let items=[{...base,id:'required',title:'Required Tokyo',completion:null as null|typeof done},{...base,id:'optional',title:'Optional Tokyo',required:false,completion:null},{...base,id:'completed',title:'Done Tokyo',completion:done},{...base,id:'skipped',title:'Skipped Tokyo',completion:{...done,status:'Skipped'}}]
 vi.mocked(apiFetch).mockImplementation(async (url,options)=>{
  if(options?.method==='PUT'){
   const body=JSON.parse(String(options.body))
   if(body.checklist_date!=='2026-10-10')throw new Error('Incorrect store-local date')
   items=items.map(item=>item.id==='required'?{...item,completion:done}:item)
   return items[0]
  }
  if(url.startsWith('/api/operations/checklist?'))return {location:{id:'all',name:'All stores'},date:'Today in each store',items}
  throw new Error('Unexpected request')
 })
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/operations?location_id=all&view=pending']}><OperationsPage/></MemoryRouter></QueryClientProvider>)
 expect(await screen.findByText('Required Tokyo')).toBeVisible()
 expect(screen.getByText('Optional Tokyo')).toBeVisible()
 expect(screen.queryByText('Done Tokyo')).not.toBeInTheDocument()
 expect(screen.queryByText('Skipped Tokyo')).not.toBeInTheDocument()
 expect(screen.queryByRole('button',{name:'Manage Checklist'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('link',{name:'Required pending 1'}))
 expect(screen.getByText('Required Tokyo')).toBeVisible()
 expect(screen.queryByText('Optional Tokyo')).not.toBeInTheDocument()
 fireEvent.click(within(screen.getByText('Required Tokyo').closest('.ops-checklist-item') as HTMLElement).getByRole('button',{name:'Complete'}))
 expect(await screen.findByRole('link',{name:'Completed 2'})).toBeVisible()
 expect(screen.queryByText('Required Tokyo')).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('link',{name:'Completed 2'}))
 expect(screen.getByText('Required Tokyo')).toBeVisible()
 expect(screen.getByText('Done Tokyo')).toBeVisible()
})
