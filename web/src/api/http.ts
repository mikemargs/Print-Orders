export class ApiError extends Error {
  status: number
  current?: unknown
  constructor(message: string, status: number, current?: unknown) { super(message); this.status = status; this.current = current }
}

let csrfToken = ''
export const setCsrfToken = (value: string) => { csrfToken = value }
export const getCsrfToken = () => csrfToken
export const clearCsrfToken = () => { csrfToken = '' }
const signal = (name:'online'|'offline') => { if(typeof window!=='undefined') window.dispatchEvent(new Event(`print-orders-${name}`)) }

export async function apiFetch<T>(path: string, options: RequestInit & { mutation?: boolean } = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const method = (options.method || 'GET').toUpperCase()
  const stateChanging = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  if ((options.mutation || stateChanging) && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try { response = await fetch(path, { ...options, headers, credentials: 'include' }) }
  catch (error) { signal('offline'); throw new ApiError(error instanceof Error ? `Cannot reach server: ${error.message}` : 'Cannot reach server', 0) }
  if ([502, 503, 504].includes(response.status)) signal('offline'); else if (response.status < 500) signal('online')
  const type = response.headers.get('content-type') || ''
  const data = type.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const detail = typeof data === 'object' && data ? (data.detail ?? data.message) : String(data)
    const message = typeof detail === 'string' ? detail : JSON.stringify(detail || `HTTP ${response.status}`)
    throw new ApiError(message, response.status, typeof data === 'object' ? data.current : undefined)
  }
  return data as T
}
