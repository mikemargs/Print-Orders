# Deployment Guide

The production design uses one Render Docker web service plus Supabase Postgres and private Supabase Storage. The same container serves the FastAPI API and compiled React PWA, so browser authentication remains same-origin. Docker Compose remains available for local development or self-hosted testing.

## 1. Create the Supabase project

Create a Supabase project and keep the database password in your password manager. In Storage, create a **private** bucket named `print-artwork` unless you plan to use a different `SUPABASE_STORAGE_BUCKET` value.

Collect these values for the Render service:

- PostgreSQL connection string for `DATABASE_URL`
- Project URL for `SUPABASE_URL`
- Server-only service-role key for `SUPABASE_SERVICE_ROLE_KEY`
- Publishable/anon key for `SUPABASE_PUBLISHABLE_KEY`
- Private bucket name for `SUPABASE_STORAGE_BUCKET`

The service-role key must never be placed in the React source, a desktop configuration file, or a public environment variable.

For the database connection, a long-running server can use the Supabase direct connection when the host supports IPv6. If the host requires IPv4, use the Supavisor **session-mode** connection string from Supabase **Connect**. For this application, use the SQLAlchemy psycopg scheme `postgresql+psycopg://` while preserving the supplied username, host, port, database, and password.

## 2. Deploy to Render

The root `render.yaml` defines the production Docker service. In Render, create a Blueprint from this repository and provide each environment variable marked `sync: false`.

Required production values include:

- `DATABASE_URL`
- `BOOTSTRAP_COMPANY_CODE`
- `BOOTSTRAP_COMPANY_PASSWORD`
- `BOOTSTRAP_ADMIN_PIN`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PUBLISHABLE_KEY`

`JWT_SECRET` is supplied as a secret Render environment value (`sync: false`). Generate a long random value before deployment. Production also sets `APP_ENV=production`, `WEB_COOKIE_SECURE=true`, and `STORAGE_BACKEND=supabase`.

The container runs `python migrate_database.py` before starting Uvicorn. On an empty database this applies every Alembic migration. On a database created by the original pre-Alembic release, the migration bootstrap detects the existing schema, stamps the frozen baseline revision, then applies later upgrades.

Use `/api/health` as the Render health-check path. It performs a real database probe, so an unavailable database makes the service unhealthy rather than reporting a false OK.

## 3. Verify the web application

After deployment, open the Render HTTPS address. The browser workflow is:

1. Enter the shared company code and company password.
2. Select the store location.
3. Select the employee and enter that employee's PIN.
4. Confirm the Dashboard, Customers, Work Orders, Reports (Supervisor/Admin), and Employees (Admin) match the signed-in role.

Browser authentication uses secure HttpOnly cookies. No bearer token is written to `localStorage` or `sessionStorage`.

## 4. Artwork uploads

Artwork metadata is authorized by FastAPI, but large file bytes go directly from the browser to the private Supabase Storage bucket using signed resumable TUS uploads. The current application default limit is 250 MiB (`262144000` bytes) and can be changed with `MAX_UPLOAD_BYTES`.

For a representative production acceptance test, upload a large PDF or print file, interrupt connectivity during the upload, and confirm the resumable upload can continue rather than restarting from zero.

## 5. Browser outage behavior

The PWA caches the application shell plus a bounded local read cache of recently loaded work orders. During an outage:

- cached work orders and customers can be listed and opened read-only;
- the UI displays the last cache/sync time;
- order/customer edits are disabled;
- reports and employee administration are disabled;
- artwork upload/download/delete is disabled;
- no browser write queue is created.

The Windows desktop application retains its separate offline create/edit synchronization workflow.

## 6. Windows installer

GitHub Actions workflow `.github/workflows/windows-installer.yml` builds the Windows application with PyInstaller and compiles `installer/PrintOrderManager.iss` with Inno Setup. The workflow uploads `PrintOrderManager-MultiStore-Setup.exe` as a private Actions artifact.

For a local Windows build, `client/build_windows_exe.bat` still creates the executable. Compile the Inno Setup file after that if you need the installer.

At first desktop launch:

1. Enter the production HTTPS server address.
2. Enter the company code and password.
3. Select that computer's store location.
4. Sign in with an employee PIN.

The long-lived desktop company token is stored with Windows Credential Manager rather than inside `client_config.json`.

## 7. Legacy data import

Before importing an old store database, make a copy of it. Import one store at a time with `client/import_legacy.bat`, synchronize completely, then compare customer/order counts before moving to the next store.

Do not operate the legacy and new systems as separate live sources of truth after migration.

## 8. Local Docker environment

For local/self-hosted testing, copy `server/.env.example` to a project-root `.env` and adjust values. For plain HTTP localhost testing use `APP_ENV=development`, `WEB_COOKIE_SECURE=false`, and `STORAGE_BACKEND=fake`; switch those to production-safe values before any internet-accessible self-hosted deployment. Docker Compose supplies its own PostgreSQL container and Caddy gateway:

```text
docker compose up -d --build
```

The API/web image is built from the repository root because the Docker build needs both `server/` and `web/`.

## 9. Release gate

Before a production release, require these checks to pass:

- GitHub `Application CI`
- Windows installer workflow
- PostgreSQL migration rehearsal
- browser sign-in/customer/order Playwright smoke test
- three-store authorization check
- desktop disconnect/reconnect synchronization test
- database restore exercise
- representative large artwork upload/resume test
