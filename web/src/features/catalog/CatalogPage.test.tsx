import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { CatalogPage } from './CatalogPage'
import { apiFetch } from '../../api/http'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { issueSession } from '../issues/testFixtures'

vi.mock('../../api/http',()=>({apiFetch:vi.fn()}))
vi.mock('../../auth/SessionContext',()=>({useSession:vi.fn()}))
vi.mock('../../offline/OnlineState',()=>({useOnline:vi.fn()}))
const tier={id:'t',min_qty:0,max_qty:null,price:1,price_unit:1,is_default:true,sort_order:0}
const base={source_item_code:null,category:'Printing',unit:'ea',currency:'USD',active:true,version:1,created_by:'e',updated_by:'e',created_at:'',updated_at:'',resolved_price:1,resolved_tier_id:'t'}
const products=[{...base,id:'tiered',name:'Volume copies',manual_price:false,tiers:[tier,{...tier,id:'t2'}]},{...base,id:'manual',name:'Custom job',manual_price:true,tiers:[]},{...base,id:'normal',name:'Envelope',manual_price:false,tiers:[tier]}]

beforeEach(()=>{
 vi.mocked(useOnline).mockReturnValue({online:true,lastSyncAt:''})
 vi.mocked(useSession).mockReturnValue({session:issueSession,loading:false,refresh:vi.fn(),setSession:vi.fn(),switchLocation:vi.fn(),logout:vi.fn()})
 vi.mocked(apiFetch).mockImplementation(async url=>{
  if(url.endsWith('/summary'))return {active_products:3,categories:1,tiered_products:1,manual_price:1,initial_import:null}
  if(url.endsWith('/categories'))return {categories:['Printing'],counts:[{category:'Printing',count:3}]}
  const params=new URL(url,'http://localhost').searchParams
  const rows=params.get('view')==='tiered'?products.slice(0,1):params.get('view')==='manual'?products.slice(1,2):products
  return {products:rows,total:rows.length}
 })
})
function Navigation(){const {search}=useLocation();const navigate=useNavigate();return <><output aria-label="Current URL">{search}</output><button onClick={()=>navigate(-1)}>Go back</button></>}
function mount(url='/catalog'){render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[url]}><Navigation/><CatalogPage/></MemoryRouter></QueryClientProvider>)}

it('opens exact pricing views and restores the previous view on Back',async()=>{
 mount()
 expect(await screen.findByText('Envelope')).toBeVisible()
 fireEvent.click(screen.getByRole('link',{name:'Tiered pricing 1'}))
 expect(await screen.findByText('1 matching')).toBeVisible()
 expect(screen.getByText('Volume copies')).toBeVisible()
 expect(screen.queryByText('Custom job')).not.toBeInTheDocument()
 expect(screen.getByLabelText('Current URL')).toHaveTextContent('?view=tiered')
 fireEvent.click(screen.getByRole('link',{name:'Manual price 1'}))
 expect(await screen.findByText('Custom job')).toBeVisible()
 expect(screen.queryByText('Volume copies')).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Go back'}))
 expect(await screen.findByText('Volume copies')).toBeVisible()
 expect(screen.getByLabelText('Current URL')).toHaveTextContent('?view=tiered')
 fireEvent.click(screen.getByRole('link',{name:'Clear summary filter'}))
 expect(await screen.findByText('Envelope')).toBeVisible()
})

it('loads bookmarked filters and renders the category drilldown',async()=>{
 mount('/catalog?view=manual&category=Printing&search=Custom')
 expect(await screen.findByText('Custom job')).toBeVisible()
 expect(screen.getByPlaceholderText('Search item code, product, or category…')).toHaveValue('Custom')
 expect(screen.getByLabelText('Catalog category filter')).toHaveValue('Printing')
 fireEvent.click(screen.getByRole('link',{name:'Categories 1'}))
 expect(await screen.findByRole('columnheader',{name:'Active products'})).toBeVisible()
 fireEvent.click(screen.getByRole('link',{name:'Printing'}))
 await waitFor(()=>expect(screen.getByLabelText('Catalog category filter')).toHaveValue('Printing'))
 expect(await screen.findByText('3 matching')).toBeVisible()
 expect(screen.getByLabelText('Current URL')).toHaveTextContent('?view=active&category=Printing')
})
