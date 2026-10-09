import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { expect, it } from 'vitest'
import { PageNavigation, SummaryCard, ViewNotice } from './SummaryCard'

function Route(){const location=useLocation();return <output aria-label="Route">{location.pathname}{location.search}</output>}
it('pages and clears a summary view while retaining the customer and store scope',()=>{
 render(<MemoryRouter initialEntries={['/orders?view=pending&customer_id=c1&location_id=&offset=250']}><Route/><SummaryCard to="/orders?view=rush">Rush 2</SummaryCard><ViewNotice/><PageNavigation total={600} limit={250} count={250}/></MemoryRouter>)
 fireEvent.click(screen.getByRole('button',{name:'Next page'}))
 expect(screen.getByLabelText('Route')).toHaveTextContent('offset=500')
 expect(screen.getByRole('button',{name:'Next page'})).toBeDisabled()
 fireEvent.click(screen.getByRole('link',{name:'Clear summary filter'}))
 expect(screen.getByLabelText('Route')).toHaveTextContent('/orders?customer_id=c1&location_id=')
 expect(screen.queryByText(/Showing:/)).not.toBeInTheDocument()
 expect(screen.getByRole('link',{name:'Rush 2'})).toHaveAttribute('href','/orders?view=rush')
})
