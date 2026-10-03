# Validation Record

## Locally verified in the implementation workspace

The current hardening + web branch has been verified with the checks available in this sandbox:

- `python -m unittest discover -s tests -v` — **64/64 tests passed**.
- `python -m compileall -q server client` — passed.
- Alembic empty-database migration and pre-Alembic upgrade rehearsal — covered by automated migration tests.
- GitHub CI also runs `python tests/postgres_smoke.py` after `alembic upgrade head` to exercise real PostgreSQL Decimal persistence, record-version row locking, and sync-event writes.
- Desktop local-cache calculations, outbox behavior, conflicts/rejections, PIN cache revocation, snapshots, and protected company-token storage — covered by automated tests.
- Tenant-scoped idempotency, store authorization, company/employee revocation, last-admin protection, login throttling, fixed-precision totals, database-aware health, and desktop/web sync propagation — covered by automated tests.
- Browser company/employee session flow, HttpOnly cookies, CSRF, customer/order REST APIs, reports/admin access, SPA routing, and private artwork attachment authorization — covered by automated tests.
- Private storage adapter behavior and production fake-storage rejection — covered by automated tests.
- Docker/Compose/Render/CI/Windows workflow configuration — covered by static deployment regression tests.
- All active TypeScript/TSX application, Playwright, and Vite configuration files — syntax-transpiled successfully with the globally available TypeScript compiler.
- Browser HTTP/session contracts — local checks cover cookie credentials, automatic CSRF on state-changing methods, offline session restoration, and deferred server logout after an offline sign-out.

## Defined but not executable in this sandbox

The sandbox cannot currently fetch npm packages and does not provide Docker, PostgreSQL CLI/server, Ruff, Windows/Inno Setup, or Render/Supabase credentials. The repository CI/staging flow therefore owns these remaining gates:

- `python -m ruff check .`
- Real PostgreSQL `alembic upgrade head` in GitHub Actions.
- `npm run typecheck`, `npm test`, `npm run lint`, and `npm run build`.
- Playwright browser E2E, including online create/order flow, offline reload/read-only behavior, and phone viewport navigation.
- Production Docker image build.
- Windows PyInstaller + Inno Setup installer artifact.
- Render deployment against Supabase Postgres/private Storage.
- Representative 250 MiB resumable artwork upload/interruption/resume test.
- PostgreSQL restore exercise and Storage recovery check.
- Three-store user acceptance and legacy-data count comparison.

Do not merge or retire the legacy production workflow until the CI and staging acceptance gates above are green and store users sign off.

- FastAPI browser security headers verified: nosniff, frame denial, no-referrer; production adds HSTS.
