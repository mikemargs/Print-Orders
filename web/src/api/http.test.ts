import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, clearCsrfToken, setCsrfToken } from './http'

afterEach(() => { vi.restoreAllMocks(); clearCsrfToken() })

describe('apiFetch', () => {
  it('always includes browser credentials and CSRF for mutations', async () => {
    setCsrfToken('csrf-value')
    const mock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }))
    await apiFetch('/api/customers', { method: 'POST', body: JSON.stringify({ company: 'A' }) })
    const [, options] = mock.mock.calls[0]
    expect(options?.credentials).toBe('include')
    expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe('csrf-value')
  })
  it('exposes the current server representation for 409 conflicts', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Version conflict', current: { version: 3 } }), { status: 409, headers: { 'content-type': 'application/json' } }))
    await expect(apiFetch('/api/customers/id', { method: 'PATCH', body: '{}' })).rejects.toMatchObject({ status: 409, current: { version: 3 } })
  })
  it('converts network failures to status zero and signals offline mode', async () => {
    const listener=vi.fn(); window.addEventListener('print-orders-offline',listener,{once:true})
    vi.spyOn(globalThis,'fetch').mockRejectedValue(new TypeError('network down'))
    await expect(apiFetch('/api/orders')).rejects.toMatchObject({status:0})
    expect(listener).toHaveBeenCalledOnce()
  })
})
