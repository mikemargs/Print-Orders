import { useState, type FormEvent } from 'react'
import { apiFetch } from '../api/http'
import type { CompanyStage, SessionInfo } from '../api/types'
import { useSession } from './SessionContext'

export function LoginPage() {
  const { setSession } = useSession()
  const [companyCode, setCompanyCode] = useState('')
  const [password, setPassword] = useState('')
  const [stage, setStage] = useState<CompanyStage | null>(null)
  const [locationId, setLocationId] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function companyLogin(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const result = await apiFetch<CompanyStage>('/api/web/auth/company', { method: 'POST', body: JSON.stringify({ company_code: companyCode, password }) })
      setStage(result)
      setLocationId(result.locations[0]?.id ?? '')
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to sign in') }
    finally { setBusy(false) }
  }

  async function employeeLogin(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const result = await apiFetch<SessionInfo>('/api/web/auth/employee', { method: 'POST', body: JSON.stringify({ employee_id: employeeId, pin, location_id: locationId }) })
      setSession(result)
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to sign in') }
    finally { setBusy(false) }
  }

  const eligible = (stage?.employees ?? []).filter(e => e.role === 'admin' || !e.location_ids.length || e.location_ids.includes(locationId))

  return <main className="login-page">
    <section className="login-card">
      <div className="brand-mark">SOH</div><h1>Store Operations Hub</h1><p className="muted">Multi-store operations, customers, print, and follow-ups</p>
      {!stage ? <form onSubmit={companyLogin} className="form-stack">
        <label>Company code<input autoFocus value={companyCode} onChange={e => setCompanyCode(e.target.value)} required /></label>
        <label>Company password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
        <button disabled={busy}>{busy ? 'Signing in…' : 'Continue'}</button>
      </form> : <form onSubmit={employeeLogin} className="form-stack">
        <p><strong>{stage.company.name}</strong></p>
        <label>Store<select value={locationId} onChange={e => { setLocationId(e.target.value); setEmployeeId('') }} required>{stage.locations.map(x => <option key={x.id} value={x.id}>{x.name} #{x.store_number}</option>)}</select></label>
        <label>Employee<select value={employeeId} onChange={e => setEmployeeId(e.target.value)} required><option value="">Choose employee…</option>{eligible.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        <label>PIN<input inputMode="numeric" type="password" value={pin} onChange={e => setPin(e.target.value)} required /></label>
        <button disabled={busy || !employeeId}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <button type="button" className="secondary" onClick={() => setStage(null)}>Back</button>
      </form>}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  </main>
}
