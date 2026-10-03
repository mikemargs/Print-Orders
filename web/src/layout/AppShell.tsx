import { NavLink, Outlet } from 'react-router-dom'
import { useSession } from '../auth/SessionContext'
import { useOnline } from '../offline/OnlineState'

export function AppShell() {
  const { session, logout } = useSession(); const {online,lastSyncAt}=useOnline()
  if (!session) return null
  const role = session.employee.role
  return <div className="app-shell">
    <header className="topbar"><div><strong>Print Order Manager</strong><span className="store-pill">{session.location.name} #{session.location.store_number}</span></div><div className="topbar-user"><span className={online?'online-state':'offline-state'}>{online?'Online':'Offline'}</span><span>{session.employee.name}</span><button className="link-button" onClick={() => void logout()}>Sign out</button></div></header>
    <aside className="sidebar" aria-label="Main navigation"><NavLink to="/" end>Dashboard</NavLink><NavLink to="/orders">Work Orders</NavLink><NavLink to="/customers">Customers</NavLink>{(role === 'supervisor' || role === 'admin') && <NavLink to="/reports">Reports</NavLink>}{role === 'admin' && <NavLink to="/employees">Employees</NavLink>}</aside>
    <main className="content">{!online&&<div className="offline-banner">Offline read-only mode. Cached work orders are available{lastSyncAt?` · last synced ${new Date(lastSyncAt).toLocaleString()}`:''}.</div>}<Outlet /></main>
  </div>
}
