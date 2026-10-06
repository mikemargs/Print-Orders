import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TasksPage } from './TasksPage'
import { listTasks, taskOptions } from '../../api/tasks'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

vi.mock('../../api/tasks', () => ({
  listTasks: vi.fn(),
  taskOptions: vi.fn(),
  taskPriorities: ['Normal','High','Urgent'],
  taskStatuses: ['Open','In Progress','Waiting','Completed','Cancelled'],
}))
vi.mock('../../auth/SessionContext', () => ({ useSession: vi.fn() }))
vi.mock('../../offline/OnlineState', () => ({ useOnline: vi.fn() }))

afterEach(() => vi.clearAllMocks())

describe('TasksPage', () => {
  it('shows company-wide tasks with store, assignment, and related records', async () => {
    vi.mocked(useSession).mockReturnValue({
      session: {
        csrf_token: 'csrf',
        company: { id: 'c', name: 'Store Co', code: 'STORE' },
        employee: { id: 'e1', name: 'Alex', role: 'admin', location_ids: ['l1','l2'], active: true },
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
    vi.mocked(useOnline).mockReturnValue({ online: true, lastSyncAt: '' })
    vi.mocked(taskOptions).mockResolvedValue({ employees: [] })
    vi.mocked(listTasks).mockResolvedValue({
      total: 1,
      tasks: [{
        id:'t1',version:1,location_id:'l2',title:'Call customer',description:'Confirm artwork',
        status:'Open',priority:'High',assigned_employee_id:'e1',due_date:'2026-10-07',
        customer_id:'c1',work_order_id:'o1',issue_id:null,created_by:'e1',updated_by:'e1',
        created_at:'2026-10-06T12:00:00Z',updated_at:'2026-10-06T12:00:00Z',completed_at:null,
        store:{id:'l2',name:'Selden',store_number:'5345',timezone:'America/New_York'},
        assignee:{id:'e1',name:'Alex',active:true},
        customer:{id:'c1',company:'Acme',first_name:'Pat',last_name:'Tester'},
        order:{id:'o1',order_number:'WO-5345-1',description:'Banner'},issue:null,
      }],
    })

    render(
      <QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}>
        <MemoryRouter><TasksPage/></MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('Call customer')).toBeInTheDocument()
    expect(screen.getByText('Selden #5345')).toBeInTheDocument()
    expect(screen.getByText('Alex')).toBeInTheDocument()
    expect(screen.getByText('Acme')).toBeInTheDocument()
    expect(screen.getByText('WO-5345-1')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'New task'})).toBeInTheDocument()
  })
})
