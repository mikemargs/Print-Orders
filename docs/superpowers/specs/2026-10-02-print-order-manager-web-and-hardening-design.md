# Print Order Manager — Hardening and Web Application Design

**Date:** 2026-10-02  
**Status:** Approved architecture; written-spec review pending  
**Repository:** `mikemargs/Print-Orders`  
**Target branch:** `audit-web-hardening` (GitHub branch creation is currently blocked by connector write permissions)

## 1. Purpose

Strengthen the existing multi-store Print Order Manager so the current Windows desktop client remains reliable and compatible, then add a production-ready browser application that can be used across Sayville (#5127), Selden (#5345), and Mt. Sinai (#3167).

The finished system will use one authoritative backend and database. The Windows desktop client will keep its offline create/edit workflow. The browser app will be a responsive React PWA with read-only cached-order access during temporary internet outages.

## 2. Success Criteria

The project is ready for production rollout when:

1. Cross-company data cannot be disclosed or mutated through sync, REST, reporting, employee-management, or file endpoints.
2. Existing Windows clients continue to synchronize through the FastAPI server after upgrade.
3. Schema changes are managed through versioned Alembic migrations rather than `create_all()` in production.
4. Automated CI runs server, desktop-cache, integration, frontend, and build checks.
5. Administrators can manage employees without accidentally leaving the company with no active administrator.
6. Employee PIN changes and deactivation invalidate cached offline credentials after the affected workstation next reconnects.
7. The web app provides customer, order, report, employee, print-ticket, and artwork-file workflows from desktop, tablet, and phone browsers.
8. Web users never receive a long-lived bearer credential in JavaScript-accessible storage.
9. Artwork files in the expected 25–250 MB range upload directly to private object storage with resumable progress.
10. During a browser outage, previously cached work orders remain viewable but cannot be edited, created, deleted, or uploaded.
11. A fresh desktop installation can initialize from a current server snapshot rather than replaying the entire historical event log.
12. Deployment can run within the existing target budget using Render plus Supabase.

## 3. Existing System to Preserve

The current repository already provides:

- Tkinter Windows desktop client
- SQLite local cache
- offline outbox and conflict handling
- FastAPI backend
- PostgreSQL production support
- employee roles and location assignments
- company and employee authentication
- optimistic record versions
- sync event feed
- reports
- legacy database import
- PyInstaller/Inno Setup build files
- Docker/Caddy deployment
- integration tests

This design extends that system instead of replacing it.

## 4. Confirmed Audit Findings

### 4.1 Critical/high-priority corrections

#### Tenant-scoped idempotency

`ProcessedOperation` is currently retrieved by operation ID alone. Idempotency must be scoped to `(company_id, operation_id)`.

The database model will use a surrogate primary key and a unique constraint on `(company_id, operation_id)`. Every lookup will include the authenticated company ID.

#### Order relationship validation on every write

Customer and location ownership are currently validated only when an order is created. Every order upsert must validate the effective customer and location, including changes to existing orders.

The service layer will resolve the proposed final record state and reject any customer/location that does not belong to the authenticated company.

#### Store authorization

Employee sessions will carry the selected `location_id`. Non-admin employees may modify orders only for a location to which they are assigned. Administrator access remains company-wide.

A newly issued desktop employee token will include `location_id`. Tokens issued by older versions that lack this claim will be required to re-authenticate before mutation.

#### Offline employee revocation

The desktop employee cache must accurately reflect deactivation and authorization changes.

The server will expose employee `auth_version`. It increments when the PIN changes or access is revoked. The desktop cache will store the version alongside the offline PIN verifier. Offline PIN verification is allowed only when:

- the cached employee is active;
- the employee is still assigned to the local store (unless administrator);
- the cached PIN verifier's auth version matches the current cached employee auth version.

Once a workstation reconnects and receives a higher auth version or inactive employee state, the old offline verifier becomes unusable.

### 4.2 Sync correctness corrections

- Later remote updates to an already-conflicted record must replace the stored server side of the conflict so the conflict screen always shows the newest server version.
- `conflict`, `invalid`, and `forbidden` sync outcomes must be represented distinctly. Invalid/forbidden changes will not be presented as ordinary version conflicts.
- Server mutation logic will live in reusable service functions so desktop sync writes and web REST writes use the same validation, calculation, authorization, versioning, and event-generation behavior.
- A snapshot endpoint will return current customers/orders plus the latest event cursor for new or reset desktop clients.

### 4.3 Data integrity

- Currency amounts (`subtotal`, `discount`, `deposit`, `total`, `balance`, line-item unit prices) will use `Decimal`/fixed precision instead of binary floating point on the server.
- Tax rate will use fixed precision.
- Pydantic request models will validate dates, text lengths, statuses, priorities, quantities, prices, and line-item structure.
- Database constraints and indexes will cover frequently queried fields and required tenant relationships.
- Work-order calculations remain server authoritative. Desktop and web clients calculate previews, but returned server totals replace local previews after synchronization.

### 4.4 Authentication hardening

- Company and employee login endpoints will receive configurable throttling/cooldown protection.
- The last active administrator cannot be demoted or deactivated.
- Web authentication will not reuse the long-lived desktop company token in localStorage/sessionStorage.
- Windows desktop company credentials will be moved out of plain JSON storage. On Windows, a credential-store/OS-protected secret mechanism will be used; non-Windows development will use an explicitly marked fallback.
- Existing bearer-token API support remains for the desktop application.

### 4.5 Health and operations

`/api/health` will verify database connectivity and return an unhealthy response when the database cannot be reached.

The application will also expose a readiness-style check appropriate for deployment health monitoring.

## 5. Database Migration Strategy

Alembic becomes the schema authority.

Production startup will run migrations before the application begins serving traffic. `Base.metadata.create_all()` remains acceptable only for isolated tests if useful, not as the production migration mechanism.

Initial migration work will capture the existing schema and then apply hardening additions, including:

- processed-operation tenant uniqueness;
- employee `auth_version`;
- fixed-precision monetary columns;
- artwork attachment records;
- any required authentication-throttle metadata;
- supporting indexes/constraints.

Every migration must be reversible when practical and tested against PostgreSQL.

## 6. Target Architecture

```text
Windows Desktop Client
        |
        | Bearer-token API + sync protocol
        v
+--------------------------+
|       FastAPI App        |
|--------------------------|
| Authentication           |
| Authorization            |
| Customer service         |
| Order service            |
| Sync adapter             |
| Reports                  |
| Attachment service       |
| Web session endpoints    |
+--------------------------+
        |             |
        | SQL         | signed upload/download authorization
        v             v
 Supabase Postgres   Supabase Storage
        ^
        |
        | REST API / HttpOnly session
        |
 React + TypeScript PWA
```

FastAPI remains the only business-logic authority. The React application will not write directly to Supabase database tables.

## 7. Backend Refactor

The existing `server/app/main.py` is too broad for the expanded application. It will be split into focused units while preserving the external desktop routes.

Proposed structure:

```text
server/app/
  main.py
  config.py
  database.py
  models.py
  schemas/
    auth.py
    customers.py
    orders.py
    employees.py
    files.py
  services/
    auth.py
    customers.py
    orders.py
    sync.py
    files.py
  routers/
    health.py
    auth.py
    sync.py
    customers.py
    orders.py
    reports.py
    employees.py
    files.py
  security.py
```

This is a targeted decomposition, not a framework rewrite.

## 8. Web Authentication

### 8.1 Login flow

The browser uses a two-stage flow consistent with the existing company/employee concept:

1. User enters company code and company password.
2. FastAPI validates them and sets a short-lived HttpOnly company-challenge cookie.
3. Browser receives the company's active locations and eligible employee list.
4. User selects location, employee, and enters the employee PIN.
5. FastAPI validates the PIN and store assignment.
6. The challenge cookie is replaced by a secure HttpOnly employee-session cookie.
7. The response also returns a non-secret CSRF token and current session metadata.

### 8.2 Cookie policy

Production session cookies will be:

- `Secure`
- `HttpOnly`
- `SameSite=Strict` where compatible with deployment
- scoped to the application host
- time limited

The React application never receives the authentication JWT itself.

State-changing browser requests require an `X-CSRF-Token` value matching the authenticated session.

### 8.3 Desktop compatibility

Existing `/api/auth/company-login`, `/api/auth/employee-login`, and bearer authentication remain available for the Windows program.

The web and desktop authentication adapters ultimately resolve to the same authenticated-company/employee context.

## 9. Web REST API

The browser uses normal resource endpoints rather than the desktop sync queue.

Representative routes:

```text
GET    /api/web/session
POST   /api/web/auth/company
POST   /api/web/auth/employee
POST   /api/web/auth/logout

GET    /api/customers
POST   /api/customers
GET    /api/customers/{id}
PATCH  /api/customers/{id}
DELETE /api/customers/{id}

GET    /api/orders
POST   /api/orders
GET    /api/orders/{id}
PATCH  /api/orders/{id}
DELETE /api/orders/{id}

GET    /api/reports/summary

GET    /api/admin/employees
POST   /api/admin/employees
PATCH  /api/admin/employees/{id}

POST   /api/orders/{id}/files/upload-authorizations
POST   /api/orders/{id}/files/finalize
GET    /api/orders/{id}/files
DELETE /api/orders/{id}/files/{file_id}
GET    /api/orders/{id}/files/{file_id}/download
```

Web updates include the record version they were based on. Stale updates return HTTP 409 and the newest server representation.

Every successful web mutation emits the same `SyncEvent` used by desktop clients so a browser change appears at every store.

## 10. Web Frontend

### 10.1 Technology

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- React Hook Form
- Zod for client-side form feedback
- Dexie/IndexedDB for offline read cache
- `vite-plugin-pwa` for installability/app-shell caching
- Uppy + TUS for large artwork uploads

### 10.2 Main screens

- Company/employee sign-in
- Dashboard
- Work Orders
- Work Order details/editing
- New Work Order
- Customers
- Customer details/editing
- Reports
- Employee administration
- Artwork/files panel
- Printable work ticket
- Offline/read-only state

### 10.3 Responsive behavior

Desktop widths use a persistent navigation rail and data tables. Tablet/phone widths switch to compact navigation and card/list presentations while preserving complete order editing.

The UI should optimize for staff speed: visible status, due date, priority, store, customer, balance, assigned employee, and artwork state.

## 11. Browser Offline Behavior

The browser PWA intentionally does **not** reproduce the desktop write queue.

When online, the application stores a bounded read cache of recently accessed/visible order data and the customer information required to display those orders.

When connectivity is lost:

- the application shell continues loading;
- an obvious offline banner is shown;
- cached orders may be searched and opened;
- cached customer information associated with those orders may be displayed;
- cached data shows its last-online timestamp;
- create/edit/delete actions are disabled;
- employee-management actions are disabled;
- reporting requiring uncached data is disabled;
- file uploads/download authorizations are disabled;
- no pending write queue is created.

Cached offline data is device-local. Logout clears browser session metadata and offers to clear the offline cache. Company policy should continue to require protected OS/browser accounts on shared store devices.

## 12. Artwork and Customer Print Files

### 12.1 Storage

Production artwork lives in a private Supabase Storage bucket.

FastAPI owns attachment authorization and metadata. The browser never receives a Supabase service-role credential.

### 12.2 Attachment model

Each attachment records at least:

- attachment ID
- company ID
- work-order ID
- storage object key
- original filename
- MIME type
- size
- uploaded-by employee ID
- created timestamp
- optional checksum
- active/deleted state

### 12.3 Upload flow

1. Authenticated user requests upload authorization for a work order.
2. FastAPI verifies tenant, store, role, filename, MIME type, and configured size ceiling.
3. FastAPI returns a short-lived signed upload authorization.
4. Browser uploads directly to Supabase Storage using resumable TUS transfer.
5. Upload progress is visible and interruption can resume.
6. Browser calls finalize.
7. FastAPI verifies/records the completed object and emits any required order update/event.

The application will target at least 250 MB files. A configurable maximum above that threshold can be selected without changing application logic.

### 12.4 Downloads

Downloads use short-lived signed URLs generated only after FastAPI verifies access.

Artwork contents are not included in the browser offline cache.

## 13. Desktop Improvements

The desktop client remains supported.

Changes include:

- tenant-safe sync operation handling;
- accurate inactive employee caching;
- `auth_version`-aware offline PIN verification;
- newest-server-copy conflict display;
- separate rejected-operation presentation;
- snapshot initialization for fresh clients;
- OS-protected company credential storage on Windows;
- improved error messaging for expired/revoked authentication;
- no loss of existing offline order/customer creation.

The desktop client can keep the current Tkinter interface during the web rollout. Large UI refactoring is outside this project's scope unless required for a corrected workflow.

## 14. Synchronization and Snapshot Design

`/api/sync/push` and `/api/sync/pull` remain the desktop incremental protocol.

A new snapshot endpoint returns:

- company-scoped current customers;
- company-scoped current work orders;
- the latest event sequence/cursor.

A newly initialized desktop cache can apply that snapshot and begin incremental pulls at the returned cursor.

Historical sync events will not be deleted blindly. Event-retention automation requires reliable knowledge of client cursors; that can be introduced later if table growth becomes operationally significant. The immediate design eliminates full-history replay for new clients without risking an offline workstation missing events.

## 15. CI and Build Pipeline

The generic PyPI release workflow will be removed.

### Linux CI

On pull requests and pushes:

1. install Python dependencies;
2. run Ruff;
3. run Python unit/integration tests;
4. start PostgreSQL service and run PostgreSQL-backed tests;
5. validate Alembic upgrade;
6. install web dependencies;
7. run frontend tests;
8. build the production React app;
9. build the production server/container image where practical.

### Windows build

A Windows GitHub Actions job will:

1. install Python;
2. install desktop dependencies and PyInstaller;
3. build `PrintOrderManager-MultiStore.exe`;
4. install/use Inno Setup;
5. compile `PrintOrderManager-MultiStore-Setup.exe`;
6. upload the installer as a GitHub Actions artifact.

No customer data or business credentials are embedded in artifacts.

## 16. Deployment

### Production

- Render hosts the FastAPI application and compiled React frontend.
- Supabase hosts PostgreSQL and private Storage.
- One public application origin is used when possible.
- HTTPS is mandatory.
- Environment secrets are supplied through the hosting providers, not committed.

### Local development

Docker/local configuration remains supported. Tests may use local PostgreSQL and a fake/local attachment storage adapter rather than requiring production Supabase credentials.

An `.env.example` file will be added and documentation updated to match the real configuration.

## 17. Backup and Recovery

Database backup guidance will be updated for Supabase-managed PostgreSQL.

Recovery requirements include:

- scheduled database backups appropriate to the selected Supabase plan;
- separate retention/export strategy where needed;
- periodic restore exercises;
- storage metadata and object-storage recovery considerations;
- backup before imports or schema migrations.

The existing local desktop cache remains a cache, not an authoritative backup.

## 18. Testing Strategy

Implementation follows test-driven development.

Required regression coverage includes:

- operation ID from another company is never returned;
- same operation ID can be safely scoped across companies;
- existing order cannot be moved to another company's customer/location;
- non-authorized store mutation is rejected;
- inactive employee cannot use refreshed offline cache;
- changed PIN invalidates old offline verifier after synchronization;
- newest remote version replaces stale conflict server payload;
- invalid/forbidden sync outcomes remain distinguishable;
- last active admin cannot be disabled/demoted;
- health fails when DB is unavailable;
- Decimal monetary calculations are deterministic;
- snapshot initializes an empty client correctly;
- web stale-version update returns 409;
- web write emits a desktop sync event;
- browser auth cookie/CSRF requirements are enforced;
- attachment authorization rejects wrong tenant/store or oversize requests.

Frontend tests cover major forms, permissions, online/offline state, and failure handling. Playwright smoke tests cover sign-in, customer creation, order creation/editing, artwork upload flow using a test adapter, and printing/navigation.

## 19. Rollout Sequence

### Phase 1 — Hardening
Security and data-integrity regression tests, tenant fixes, authorization fixes, employee revocation fixes, sync fixes, health checks.

### Phase 2 — Schema and CI
Alembic baseline/migrations, Decimal conversion, real PostgreSQL test path, `.env.example`, corrected CI and Windows installer workflow.

### Phase 3 — Shared backend services
Refactor current route logic into shared service functions and add REST endpoints while preserving the desktop sync contract.

### Phase 4 — Artwork storage
Attachment schema, storage abstraction, Supabase signed/resumable uploads, signed downloads, tests.

### Phase 5 — React PWA
Authentication, dashboard, orders, customers, reports, employees, attachments, work-ticket printing, responsive design.

### Phase 6 — Offline web cache
PWA installability, IndexedDB read cache, explicit read-only outage state and cache lifecycle controls.

### Phase 7 — Production verification
Cross-store tests, disconnect/reconnect tests, migration rehearsal, PostgreSQL restore exercise, large-file upload test, Windows installer build, Render/Supabase deployment documentation, and user acceptance.

## 20. Non-goals for This Cycle

To keep the project deployable and maintainable, this cycle will not add:

- browser offline editing;
- collaborative live cursor/editor behavior;
- payment-card storage or payment processing;
- customer self-service portal;
- automated SMS/email marketing;
- a full rewrite of the Tkinter desktop UI;
- direct React access to database tables;
- public artwork buckets.

These can be separate future projects.

## 21. Compatibility Rule

The central rule for all implementation work is:

> A web feature must not bypass the business logic or event generation required by the desktop synchronization system.

Desktop and web are two clients of the same application, not two separate order systems.
