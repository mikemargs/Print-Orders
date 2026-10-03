# Hardening and Migrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the current FastAPI/desktop system, introduce versioned database migrations, and preserve the Windows sync contract.

**Architecture:** Fix authorization and synchronization correctness at the server boundary first. Introduce Alembic before schema changes, then evolve employee authentication, monetary precision, conflict handling, credential storage, and snapshot initialization behind regression tests.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL 17, SQLite, unittest/TestClient, Ruff.

**Spec:** `docs/superpowers/specs/2026-10-02-print-order-manager-web-and-hardening-design.md`

## Global Constraints

- Preserve current desktop auth/bootstrap/sync endpoints.
- Production schema changes use Alembic, not `create_all()`.
- Server calculations are authoritative.
- Do not modify `main`.
- Use test-first development for behavior changes.

## Review Focus

- Reused sync operation IDs across companies must never collide or leak results.
- Existing orders cannot be reassigned to another company's customer/location.
- PIN changes/deactivation must invalidate stale offline login after reconnect.
- Repeated remote edits must leave the newest server conflict payload.
- Fresh clients initialize from snapshot rather than replaying all history.

---

### Task 1: Add migration-managed schema

**Files:**
- Create: `server/alembic.ini`
- Create: `server/alembic/env.py`
- Create: `server/alembic/script.py.mako`
- Create: `server/alembic/versions/<baseline>.py`
- Modify: `server/requirements.txt`
- Modify: `server/app/main.py`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Consumes current `Base.metadata` and `DATABASE_URL`.
- Produces `alembic upgrade head` as the production upgrade command.

- [ ] **Step 1: Write failing tests** for empty-database upgrade and production startup without runtime `create_all()`.
- [ ] **Step 2: Run** `python -m unittest tests.test_migrations -v`; expected FAIL because Alembic config is absent.
- [ ] **Step 3: Add** `alembic>=1.14,<2`, Alembic config, and a baseline migration.
- [ ] **Step 4: Remove** production reliance on `Base.metadata.create_all(engine)`; keep test schema setup isolated.
- [ ] **Step 5: Run** migration tests and `python -m unittest discover -s tests -v`; expected PASS.
- [ ] **Step 6: Commit** `chore: add versioned database migrations`.

### Task 2: Scope processed sync operations by company

**Files:**
- Modify: `server/app/database.py`
- Create: `server/alembic/versions/<processed_operation_scope>.py`
- Modify: `server/app/main.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- `ProcessedOperation.row_id: str` primary key.
- `ProcessedOperation.operation_id: str`.
- Unique `(company_id, operation_id)`.

- [ ] Write failing two-company same-operation-ID regression test.
- [ ] Run targeted test; expected FAIL under global-ID behavior.
- [ ] Migrate old `id` to `operation_id`, populate `row_id`, add unique constraint.
- [ ] Query processed operations by authenticated company + operation ID.
- [ ] Run targeted and full suites.
- [ ] Commit `fix: scope sync idempotency to company`.

### Task 3: Enforce effective order relationships and store authorization

**Files:**
- Modify: `server/app/security.py`
- Modify: `server/app/main.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- `make_token(..., location_id: str = "") -> str`.
- Employee tokens include `location_id`.
- `validate_order_relationships(db, company_id, customer_id, location_id) -> None`.
- `assert_order_store_access(claims, location_id) -> None`.

- [ ] Add failing tests for foreign-company customer/location updates, unassigned-store mutation, admin override, and pre-location tokens.
- [ ] Verify failures.
- [ ] Include selected location in newly issued employee JWTs.
- [ ] Merge existing record + incoming payload before validating the effective customer/location.
- [ ] Reject unauthorized location mutation before ORM assignment.
- [ ] Run full suite and commit `fix: enforce order tenant and store authorization`.

### Task 4: Version offline employee credentials

**Files:**
- Modify: `server/app/database.py`
- Create: `server/alembic/versions/<employee_auth_version>.py`
- Modify: `server/app/main.py`
- Modify: `client/local_store.py`
- Modify: `client/app.py`
- Modify: `tests/test_server.py`
- Modify: `tests/test_local_store.py`

**Interfaces:**
- `Employee.auth_version: int`.
- `public_employee()` returns `auth_version`.
- `cache_employee_pin(employee_id: str, pin: str, auth_version: int) -> None`.
- PIN cache stores auth version.

- [ ] Add failing tests that bootstrap includes inactive employee state and PIN/deactivation increments auth version.
- [ ] Add failing local test showing version mismatch invalidates cached PIN.
- [ ] Add schema migration and server increment behavior.
- [ ] Upgrade existing SQLite cache additively.
- [ ] Deny offline login for inactive/unassigned/version-mismatched employees.
- [ ] Run server/local/full suites.
- [ ] Commit `fix: revoke stale offline employee credentials`.

### Task 5: Correct conflict and rejected-operation handling

**Files:**
- Modify: `client/local_store.py`
- Modify: `client/app.py`
- Modify: `tests/test_local_store.py`

**Interfaces:**
- Sync issue records distinguish `conflict`, `invalid`, and `forbidden`.
- Later remote events replace stored `server_payload`.
- Only true conflicts permit keep-local/keep-server resolution.

- [ ] Write failing tests for newest server payload and rejection categories.
- [ ] Verify failures.
- [ ] Add additive local-cache schema migration if a category/status field is needed.
- [ ] Change existing-conflict upsert to update the server payload instead of `DO NOTHING`.
- [ ] Update Sync Issues UI actions/copy by category.
- [ ] Run tests and commit `fix: preserve latest conflict state and rejected sync errors`.

### Task 6: Use fixed-precision money and typed sync payload validation

**Files:**
- Modify: `server/app/database.py`
- Create: `server/alembic/versions/<numeric_money>.py`
- Modify: `server/app/main.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Monetary columns use SQL `Numeric`.
- Calculation uses `Decimal` and cent rounding.
- Typed line-item/order schemas validate dates, statuses, priorities, quantities, prices, and text lengths.

- [ ] Add failing tests for decimal edge cases, fractional quantities, negative inputs, invalid status/priority, and malformed dates.
- [ ] Verify at least one current regression fails.
- [ ] Add Pydantic payload schemas.
- [ ] Migrate numeric columns and calculate with Decimal.
- [ ] Preserve JSON-number-compatible serialized totals for desktop.
- [ ] Run desktop round-trip/full suite and commit `fix: use validated fixed precision order totals`.

### Task 7: Protect the final administrator and throttle login attempts

**Files:**
- Modify: `server/app/security.py`
- Modify: `server/app/main.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Final active admin cannot be disabled/demoted.
- Configurable bounded login throttle returns HTTP 429 after threshold.

- [ ] Add failing last-admin and repeated-bad-login tests.
- [ ] Verify failures.
- [ ] Add last-admin transactional guard.
- [ ] Add injectable/resettable throttle abstraction with environment-configured limits.
- [ ] Verify successful login resets relevant failure state.
- [ ] Run full suite and commit `fix: harden administrator and login controls`.

### Task 8: Add DB-aware health and client snapshot

**Files:**
- Modify: `server/app/main.py`
- Modify: `client/sync_engine.py`
- Modify: `client/local_store.py`
- Modify: `tests/test_server.py`
- Modify: `tests/test_local_store.py`

**Interfaces:**
- `GET /api/health` probes database.
- `GET /api/sync/snapshot` returns `customers`, `orders`, and `cursor`.
- `LocalStore.apply_snapshot(snapshot: dict) -> None`.

- [ ] Add failing unhealthy-DB and snapshot tests.
- [ ] Verify failures.
- [ ] Implement `SELECT 1` health probe.
- [ ] Implement tenant-scoped current-state snapshot and latest cursor.
- [ ] Apply snapshot atomically to empty/reset local cache.
- [ ] Update initial sync rule to snapshot before incremental pulls when appropriate.
- [ ] Run full suite and commit `feat: add database health and sync snapshots`.

### Task 9: Protect desktop company token

**Files:**
- Create: `client/credential_store.py`
- Modify: `client/config.py`
- Modify: `client/app.py`
- Modify: `client/requirements.txt`
- Create: `tests/test_config.py`

**Interfaces:**
- `load_company_token() -> str`.
- `save_company_token(token: str) -> None`.
- `delete_company_token() -> None`.
- JSON config contains no token.

- [ ] Add failing tests proving token is absent from `client_config.json`.
- [ ] Verify failure.
- [ ] Implement Windows OS-protected credential storage with isolated non-Windows test fallback.
- [ ] Update connect/reconnect flows to use credential abstraction.
- [ ] Run tests and PyInstaller import smoke test.
- [ ] Commit `fix: protect desktop connection credentials`.

### Task 10: Hardening verification and documentation

**Files:**
- Modify: `VALIDATION.md`
- Modify: `SECURITY_AND_BACKUPS.md`
- Modify: `README.md`

- [ ] Run `python -m ruff check .`.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run PostgreSQL empty-DB migration.
- [ ] Run upgrade from a captured pre-change schema fixture.
- [ ] Run desktop/server round-trip.
- [ ] Record actual results and commit `docs: record hardened system validation`.
