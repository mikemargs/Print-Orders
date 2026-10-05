# Customer Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a manual customer resolution tracker to the existing multi-store website.

**Architecture:** Extend the React website and FastAPI backend with a dedicated issue service and additive database migration. Reuse sessions, customer records, store selection, styling, and existing deployment.

**Tech Stack:** React, TypeScript, TanStack Query, FastAPI, SQLAlchemy, Alembic, unittest, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-05-customer-issues-design.md`

## Global Constraints

- Manual logging only; no email sending/import, SMS, customer portal, automatic reminders, complaint attachments, or refund-payment processing in this version.
- All reads and writes enforce company isolation on the server.
- Employees can read company-wide cases; writes require the active store, except administrators.
- First version requires a connection to load and edit issues; do not add persistent offline caching of complaint histories.
- Preserve the existing pending-order dashboard and legacy desktop sync.
- Follow-up dates use the case store timezone; timestamps are UTC.
- Version checks, atomic audit history, and idempotent communication retries are mandatory.

## Review Focus

- A request lost after commit must not duplicate a communication on retry (Task 2).
- A concurrent edit must preserve both employees' information or return a conflict (Task 2).
- A store/customer change must not leave an incompatible order link (Task 2).
- Midnight UTC must not mark New York follow-ups overdue prematurely (Task 3).
- Switching employee identity must not expose the previous employee's cached case data (Task 4).

## File ownership and contracts

- `server/app/database.py`: CustomerIssue and IssueActivity models.
- `server/alembic/versions/0007_customer_issues.py`: additive tables/indexes.
- `server/app/schemas/issues.py`: strict input schemas and enums.
- `server/app/services/issues.py`: validation, scope, transactional mutations and serialization.
- `server/app/routers/issues.py`: authenticated HTTP interface.
- `server/app/main.py`: register router.
- `web/src/api/issues.ts`: TypeScript contracts and request functions.
- `web/src/features/issues/`: list, editor/detail, timeline and query hooks.
- `web/src/App.tsx`, `web/src/layout/AppShell.tsx`: routes/navigation.
- `web/src/features/dashboard/DashboardPage.tsx`: compact case summary.
- `web/src/auth/SessionContext.tsx`: query isolation at logout/identity changes if not already enforced.
- Existing frontend stylesheet: reuse component classes; add responsive case styles only as needed.

### Task 1: Persistent models and input contracts

**Files:** database model, migration and schemas above; `tests/test_issue_models.py`, `tests/test_migrations.py`.

**Interfaces:** CustomerIssue and IssueActivity match the spec. `IssueCreate`, `IssueUpdate`, `CommunicationCreate` are strict Pydantic schemas. PATCH requires `version`; communication requires `operation_id`, `channel`, `occurred_at`, `summary`, with optional next action/date and version when changing case fields.

- [ ] Write failing model/schema tests: unique `(company_id, reference)`, unique `(company_id, operation_id)` for communication activities, invalid enum/date rejection, blank resolution rejection, optional order and assignee, nonblank title/description/summary with bounded lengths. Use limits title 200, description 10000, summary/resolution 10000, next action 2000, reference 50. Trim before nonblank validation.
- [ ] Run `python -m unittest discover -s tests -p 'test_issue_models.py' -v`; confirm failure reflects missing feature.
- [ ] Implement UUID keys, spec fields, foreign keys and indexes. Add nullable follow-up date, aware timestamps and JSON field changes. Use the migration's current predecessor verified from repository head; do not alter an existing migration.
- [ ] Run model tests and `python -m unittest discover -s tests -p 'test_migrations.py' -v`; verify additive upgrade preserves seeded customers/orders.
- [ ] Commit `feat: add customer issue models and schemas`.

### Task 2: Transactional case lifecycle and communication history

**Files:** `server/app/services/issues.py`, `tests/test_issue_services.py`.

**Interfaces:** `create_issue(db, auth, data) -> CustomerIssue`; `update_issue(db, auth, issue_id, version, data) -> CustomerIssue`; `append_communication(db, auth, issue_id, data) -> IssueActivity`; `serialize_issue(db, row) -> dict`; `serialize_activity(row) -> dict`. Services flush but router owns commit/rollback; use existing service exception types.

- [ ] Write failing tests: tenant isolation, employee active-store writes, administrator cross-store writes, same-company active assignee eligibility, active customer/store, linked order matching customer/store, author derived from auth, history of tracked field changes, resolve summary and reopen reason, resolved timestamp lifecycle.
- [ ] Add tests: replay the same operation ID and payload returns original activity without repeated follow-up changes; reuse with different payload/case returns conflict; stale version does not create history; two concurrent updates accept only one; changing customer/store rejects incompatible retained link; communication text preserves literal punctuation/markup as text.
- [ ] Run `python -m unittest discover -s tests -p 'test_issue_services.py' -v`; confirm failures.
- [ ] Implement shared company lookup and write-scope checks. Allocate references as `CI-` plus UUID hex (unique constraint), use atomic conditional UPDATE on version, and atomically create audit rows. Reopening sets Open and clears resolved timestamp while keeping prior resolution in immutable history. Logs may be added to resolved cases; status remains Resolved unless explicitly reopened.
- [ ] Run service tests with transactions and a separate-session conflict test; all pass.
- [ ] Commit `feat: implement customer issue lifecycle and manual logs`.

### Task 3: Secured API, complete summaries and date rules

**Files:** issue router, main router registration, `tests/test_issue_routes.py`.

**Interfaces:** `/api/issues` GET/POST; `/api/issues/summary` GET before dynamic route; `/api/issues/{id}` GET/PATCH; `/api/issues/{id}/activities` GET/POST. List returns `{issues,total}`; summary returns `{open,overdue,high_priority,assigned_to_me}`; activities returns `{activities,total}`. List query supports search, location_id, status, priority, category, assigned_employee_id, customer_id, unresolved_only, limit (1–250), offset. Summary accepts the same filters without pagination. Activities are ordered by occurred_at, recorded_at, ID with bounded pagination.

- [ ] Write failing HTTP tests for unauthenticated access, missing CSRF, foreign-company IDs, employee write scope, 409 current case response, validation errors, pagination totals, resolve/reopen and full history.
- [ ] Add summary tests with over 250 cases and a fixed instant crossing UTC midnight: New York follow-up today is not overdue, yesterday is overdue, Resolved never overdue. Include unassigned/no-date cases and inactive historical employee display.
- [ ] Run `python -m unittest discover -s tests -p 'test_issue_routes.py' -v`; confirm failures.
- [ ] Implement routes using existing web session dependencies, rollback on service errors, server-calculated counters over all filtered rows, store-local dates with ZoneInfo. High priority means High or Urgent and unresolved. Search title/reference/customer names/company, escape literal wildcard characters in search. Return display information scoped to each authorized case; enforce company scope before all related lookups.
- [ ] Run route tests and existing web-session/auth tests; pass.
- [ ] Commit `feat: expose authenticated customer issue API`.

### Task 4: Customer Issues screens and app integration

**Files:** `web/src/api/issues.ts`; `web/src/features/issues/{IssuesPage,IssueEditor,IssueTimeline,IssueSummary}.tsx`; `web/src/features/issues/useIssues.ts`; App, AppShell, DashboardPage, SessionContext; `web/src/features/issues/IssuesPage.test.tsx`, `web/src/features/issues/IssueEditor.test.tsx`.

**Interfaces:** API functions `listIssues(filters)`, `getIssue(id)`, `createIssue(input)`, `updateIssue(id,input)`, `listActivities(id,offset)`, `logCommunication(id,input)`, `getIssueSummary(filters)`. Types `CustomerIssue`, `IssueActivity`, `IssueFilters`, `IssueSummary` mirror Task 3. Routes `/issues`, `/issues/new`, `/issues/:id`.

- [ ] Write failing UI tests for navigation, filtered/paginated list, accurate counts, empty/error/loading states, create from existing/new customer, optional order association, log occurrence time/channel, follow-up edit, resolve/reopen, immutable timeline, permission-disabled write controls.
- [ ] Add tests preserving unsaved text on server failure/conflict, literal note rendering, offline-disabled controls/stale indicator, identity cache clearing and store-switch invalidation.
- [ ] Run `npm test --prefix web -- IssuesPage IssueEditor`; confirm failures.
- [ ] Implement typed requests using apiFetch and session-scoped issue query keys. Poll visible online queries every 30 seconds and refresh on focus; invalidate all issue/detail/activity/summary queries after writes. Use crypto.randomUUID for each communication submission and retain it on uncertain retry; reset only after success or a deliberate changed submission. Use existing customer/editor and order lists rather than duplicate customer data. Load timeline pages explicitly. Convert entered occurrence datetime in the store timezone correctly, including daylight-saving boundaries; use an explicit timezone offset choice if the wall time is ambiguous.
- [ ] Integrate navigation and a compact Main Dashboard summary. Show all company cases by default with store names; default new-case store to active store. Preserve current styling, responsive forms and accessible labels. Clear relevant query cache on logout/identity change. Do not persist issues in IndexedDB or service-worker API cache.
- [ ] Run frontend tests, `npm run typecheck --prefix web`, `npm run lint --prefix web`, `npm run build --prefix web`; pass.
- [ ] Commit `feat: add customer issues workspace`.

### Task 5: End-to-end review and release handoff

**Files:** `web/e2e/customer-issues.spec.ts` (use actual existing e2e directory convention), `DEPLOYMENT_GUIDE.md`, `README.md`.

**Interfaces:** Complete existing app flow, same deployment and migration command documented by the repository.

- [ ] Add a failing browser journey using fictional customers: sign in, create case, append contact and follow-up, switch permitted store, open case read-only when not active, resolve/reopen, and return to dashboard. Assert customer data never leaks after logout. Cover mobile layout and keyboard form completion.
- [ ] Run targeted Playwright journey with existing test harness; fix integration defects and rerun until it passes.
- [ ] Document migration-before-serving sequence, manual logging, case permissions, online-only case behavior, and rollback compatibility (older app ignores additive tables; retain data). Run `python -m unittest discover -s tests -v`, `npm test --prefix web`, `npm run typecheck --prefix web`, `npm run lint --prefix web`, `npm run build --prefix web`, and browser tests via existing harness. Record actual pass/failure evidence; do not claim checks not run.
- [ ] Review full diff against spec for authorization, race conditions, query-cache isolation, timezone conversion and regressions. Resolve findings before final readiness claim.
- [ ] Commit docs and journey, publish feature branch using GitHub, and create a draft PR with scope, migration notes and validation. Do not merge or deploy production without user instruction.

## Execution handoff

Recommend native execution: the five tasks share data/API contracts and benefit from one implementer maintaining continuity. Alternative: subagent-driven execution provides independent review per task with additional context cost. User must review this plan and select the method before product implementation under the writing-plans workflow.
