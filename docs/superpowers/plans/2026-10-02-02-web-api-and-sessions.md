# Web API and Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add browser-ready REST APIs and secure cookie-session authentication while preserving desktop sync behavior.

**Architecture:** Extract shared customer/order mutation services from route handlers. Desktop sync and new REST routes call the same services so validation, authorization, versions, totals, and `SyncEvent` generation cannot diverge.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic 2.x, secure HttpOnly cookies, CSRF validation, unittest/TestClient.

**Spec:** `docs/superpowers/specs/2026-10-02-print-order-manager-web-and-hardening-design.md`

## Global Constraints

- FastAPI is the only business-logic authority.
- React never writes directly to Supabase tables.
- Desktop bearer routes remain compatible.
- Web JWT/session secrets never enter localStorage/sessionStorage.
- State-changing web requests require CSRF validation.

## Review Focus

- Cross-company IDs in REST URLs must not leak resource existence.
- Stale versions return 409 with current representation.
- Cookie without CSRF cannot mutate.
- Role/store changes are rechecked against current DB state.
- One web mutation emits exactly one desktop-compatible sync event.

---

### Task 1: Centralize authenticated request context

**Files:** Create `server/app/auth_context.py`; modify `security.py`, `main.py`; test `tests/test_web_auth.py`.

**Interfaces:** `AuthContext(company_id, employee_id, role, location_id, auth_version)` plus desktop/web resolvers.

- [ ] Write failing active/role/auth-version tests.
- [ ] Verify failure.
- [ ] Implement shared context resolution.
- [ ] Adapt existing desktop dependencies without changing responses.
- [ ] Run server tests and commit `refactor: centralize authenticated request context`.

### Task 2: Extract customer/order mutation services

**Files:** Create `server/app/services/customers.py`, `orders.py`, `sync_events.py`; modify `main.py`; test `tests/test_services.py`.

**Interfaces:** `create/update/delete_customer(...)`, `create/update/delete_order(...)`; every successful mutation emits one event.

- [ ] Write failing tenant/version/calculation/delete/event-count tests.
- [ ] Verify failures.
- [ ] Implement services.
- [ ] Route `/api/sync/push` through service adapter.
- [ ] Run desktop sync regression/full suite.
- [ ] Commit `refactor: share customer and order mutation services`.

### Task 3: Add secure web session lifecycle

**Files:** Create `server/app/routers/web_auth.py`, `server/app/web_sessions.py`; modify `main.py`; test `tests/test_web_auth.py`.

**Interfaces:** `POST /api/web/auth/company`, `POST /api/web/auth/employee`, `GET /api/web/session`, `POST /api/web/auth/logout`.

- [ ] Add failing cookie attribute, expiry, logout, auth-version, and CSRF tests.
- [ ] Verify failures.
- [ ] Implement short-lived company challenge cookie.
- [ ] Implement secure HttpOnly employee session bound to location/auth_version.
- [ ] Return non-secret CSRF token in session metadata.
- [ ] Run tests and commit `feat: add secure browser sessions`.

### Task 4: Customer REST API

**Files:** Create `server/app/routers/customers.py`, `server/app/schemas/customers.py`; test `tests/test_web_customers.py`.

**Interfaces:** list/search, create, get, patch, delete; updates/deletes carry version.

- [ ] Write failing CRUD/search/tenant/409/CSRF tests.
- [ ] Verify failures.
- [ ] Implement router via customer service only.
- [ ] Verify corresponding sync event is visible to desktop pull.
- [ ] Commit `feat: add customer REST API`.

### Task 5: Work-order REST API

**Files:** Create `server/app/routers/orders.py`, `server/app/schemas/orders.py`; test `tests/test_web_orders.py`.

**Interfaces:** list filters for store/status/priority/due/search/customer; CRUD; stale writes return 409 with `current`.

- [ ] Write failing filter/CRUD/store/tenant/version/CSRF tests.
- [ ] Verify failures.
- [ ] Implement router via order service only.
- [ ] Verify authoritative totals and one event.
- [ ] Commit `feat: add work order REST API`.

### Task 6: Reports and employee admin through browser sessions

**Files:** Create focused reports/employees routers or refactor current handlers; test `tests/test_web_admin.py`.

- [ ] Add failing cookie-auth and role/store tests.
- [ ] Verify failures.
- [ ] Reuse existing report/admin service behavior through both auth adapters.
- [ ] Verify desktop API client compatibility.
- [ ] Commit `refactor: expose reports and employee admin to web sessions`.

### Task 7: Define SPA/API routing boundary and document contract

**Files:** Create `server/app/routers/web.py`, `docs/API_WEB.md`; modify `main.py`; test `tests/test_web_routes.py`.

- [ ] Write failing test that `/api/*` never falls through to SPA.
- [ ] Implement safe static/SPA fallback when build assets exist.
- [ ] Document exact session/version/error contract for frontend.
- [ ] Run full suite and commit `docs: finalize browser API contract`.
