# Browser API Contract

The browser client uses the same FastAPI application as the Windows desktop client. Browser code must call `/api/*`; it must never write directly to PostgreSQL or Supabase database tables.

## Authentication

Browser authentication is two-stage:

1. `POST /api/web/auth/company` with `company_code` and `password`.
   - Sets short-lived `pom_company_challenge` as `HttpOnly`, `Secure`, `SameSite=Strict`.
   - Returns company, active locations, and active employees.
2. `POST /api/web/auth/employee` with `employee_id`, `pin`, and `location_id`.
   - Requires the challenge cookie.
   - Replaces it with `pom_session`, also `HttpOnly`, `Secure`, `SameSite=Strict`.
   - Returns a non-secret CSRF token plus employee/location/company metadata.

`GET /api/web/session` restores browser session metadata. Employee active state, company active state, store assignment, role, and `auth_version` are re-read from the database on authenticated requests, so access changes invalidate stale sessions.

`POST /api/web/auth/logout` requires `X-CSRF-Token` when a session exists and clears browser auth cookies.

Browser JavaScript must not store bearer tokens or session JWTs in `localStorage` or `sessionStorage`.

## CSRF

Every state-changing request made with the browser cookie session must send:

`X-CSRF-Token: <csrf_token returned by the session endpoint>`

Missing or invalid CSRF produces HTTP `403`.

Desktop bearer-token calls do not use CSRF.

## Customers

- `GET /api/customers?search=&limit=&offset=`
- `POST /api/customers`
- `GET /api/customers/{customer_id}`
- `PATCH /api/customers/{customer_id}`
- `DELETE /api/customers/{customer_id}`

Updates/deletes carry the current `version`. A stale write returns HTTP `409` with:

```json
{
  "detail": "Version conflict",
  "current": {"id": "...", "version": 2}
}
```

Cross-company records are never returned as usable resources.

## Work orders

- `GET /api/orders`
- `POST /api/orders`
- `GET /api/orders/{order_id}`
- `PATCH /api/orders/{order_id}`
- `DELETE /api/orders/{order_id}`

Supported list filters include store/location, status, priority, customer, and search. Updates/deletes carry `version`; stale writes return the same `409` shape used by customers.

All order totals are calculated by the server. Browser-provided subtotal/total/balance values are not authoritative.

## Reports and employee administration

Existing routes remain available to the desktop bearer client and additionally accept the secure browser session:

- `GET /api/reports/summary`
- `GET /api/admin/employees`
- `POST /api/admin/employees`
- `PATCH /api/admin/employees/{employee_id}`

Browser writes require CSRF. Existing desktop bearer behavior is preserved.

## Desktop synchronization compatibility

Successful browser customer/order mutations call the same service layer as desktop sync and emit the same `SyncEvent` representation. A desktop client therefore receives browser changes through `/api/sync/pull` without a separate translation layer.

## SPA routing boundary

All known `/api/*` routes are registered before the SPA fallback. Unknown `/api/*` paths always return API `404`; they never receive `index.html`.

Non-API paths such as `/orders/<id>` may fall back to `web/dist/index.html` after the React build exists. Static file paths are constrained to the configured web distribution directory.
