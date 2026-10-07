import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useSession } from '../auth/SessionContext'
import { useOnline } from '../offline/OnlineState'

export function AppShell() {
  const { session, logout, switchLocation } = useSession()
  const { online, lastSyncAt } = useOnline()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [switching, setSwitching] = useState(false)
  const [storeError, setStoreError] = useState('')
  if (!session) return null

  const role = session.employee.role
  const allowedLocations = session.locations.filter(location =>
    role === 'admin' ||
    !session.employee.location_ids.length ||
    session.employee.location_ids.includes(location.id),
  )

  async function changeStore(locationId: string) {
    if (!locationId || locationId === session!.location.id) return
    setSwitching(true)
    setStoreError('')
    try {
      await switchLocation(locationId)
      await queryClient.invalidateQueries()
      navigate('/', { replace: true })
    } catch (error) {
      setStoreError(error instanceof Error ? error.message : 'Unable to switch stores')
    } finally {
      setSwitching(false)
    }
  }

  return <div className="app-shell">
    <header className="topbar">
      <div className="topbar-brand">
        <strong>Store Operations Hub</strong>
        {allowedLocations.length > 1
          ? <select
              className="store-switch"
              aria-label="Active store"
              value={session.location.id}
              disabled={!online || switching}
              onChange={event => void changeStore(event.target.value)}
            >
              {allowedLocations.map(location =>
                <option key={location.id} value={location.id}>
                  {location.name} #{location.store_number}
                </option>,
              )}
            </select>
          : <span className="store-pill">{session.location.name} #{session.location.store_number}</span>}
      </div>
      <div className="topbar-user">
        <span className={online ? 'online-state' : 'offline-state'}>{online ? 'Online' : 'Offline'}</span>
        <span>{session.employee.name}</span>
        <button className="link-button" onClick={() => void logout()}>Sign out</button>
      </div>
    </header>
    <aside className="sidebar" aria-label="Main navigation">
      <NavLink to="/" end>Main Dashboard</NavLink>
      <NavLink to="/orders">Work Orders</NavLink>
      <NavLink to="/customers">Customers</NavLink>
      <NavLink to="/tasks">Tasks & Follow-Ups</NavLink>
      <NavLink to="/issues">Customer Issues</NavLink>
      {(role === 'supervisor' || role === 'admin') && <NavLink to="/reports">Reports</NavLink>}
      {role === 'admin' && <NavLink to="/employees">Employees</NavLink>}
    </aside>
    <main className="content">
      {storeError && <div className="error" role="alert">{storeError}</div>}
      {!online && <div className="offline-banner">
        Offline read-only mode. Cached work orders are available
        {lastSyncAt ? ` · last synced ${new Date(lastSyncAt).toLocaleString()}` : ''}.
        Store switching is available again when the connection returns.
      </div>}
      <Outlet />
    </main>
  </div>
}
