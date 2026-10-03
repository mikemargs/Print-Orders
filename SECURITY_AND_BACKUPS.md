# Security and Backups

## Authentication

The company code/password establishes the company context. Employees then authenticate with individual PINs. PINs are stored as salted PBKDF2-SHA256 hashes; plaintext PINs are not stored.

Desktop employee tokens are bound to the selected store and the employee's `auth_version`. Browser sessions use secure HttpOnly cookies and CSRF tokens rather than exposing JWTs to JavaScript storage. The server rechecks company status, employee status, role, store assignment, and authentication version on protected requests.

Changing an employee PIN, role, store access, or active state increments `auth_version`. After a desktop workstation reconnects and refreshes bootstrap data, a stale offline PIN verifier is rejected. The browser session becomes invalid as soon as its version no longer matches the database.

The final active administrator cannot be demoted or deactivated.

## Login throttling

Company-password and employee-PIN endpoints have application-level attempt throttling. Production should also use the hosting provider's network protections and should not treat process-local throttling as the only defense against distributed attacks.

## Desktop credential protection

`client_config.json` contains non-secret connection metadata only. On Windows, the company bearer token is stored through Windows Credential Manager. A development-only file fallback exists for non-Windows test environments and is not the production credential strategy.

Use individual Windows accounts, full-disk encryption, automatic screen locking, current endpoint protection, and restricted administrator access on store computers.

## Browser offline cache

The PWA stores a bounded local read cache of recently viewed/loaded work orders and supporting customer records in IndexedDB. Browser outage mode is intentionally read-only. Artwork bytes and signed file URLs are not stored for offline use. The non-secret CSRF value may be retained with cached session metadata solely so an offline sign-out can clear the HttpOnly server session after connectivity returns; the session cookie/JWT is never placed in IndexedDB. Signing out clears the browser data cache by default.

Shared computers must still use protected OS/browser profiles because any offline cache is local to that browser profile.

## Network and secrets

- Production traffic must use HTTPS.
- `WEB_COOKIE_SECURE=true` is required in production.
- Do not expose PostgreSQL directly to the public internet.
- Never place `SUPABASE_SERVICE_ROLE_KEY`, database credentials, company passwords, or JWT secrets in the frontend bundle.
- Keep the Supabase artwork bucket private.
- Rotate credentials after suspected exposure.

## Database migrations

Schema changes are versioned with Alembic. The production container runs `server/migrate_database.py` before Uvicorn. Back up production before a schema upgrade or bulk import and rehearse migrations against a non-production copy first.

## Database backups

For Supabase production, configure backup retention appropriate to the selected plan and keep an additional export strategy if the business requires retention beyond the provider's included window. A database backup must be periodically restored into a non-production database to prove it is usable.

For local Docker PostgreSQL, `server/backup_database.sh` remains available for compressed `pg_dump` backups.

A practical policy is:

- daily database restore points;
- monthly longer-term retention;
- at least one copy outside the primary hosting failure domain where required;
- quarterly restore exercises;
- backup before migrations, imports, or large administrative changes.

## Artwork storage recovery

Database backups contain artwork **metadata**, not the Storage object bytes. Supabase Storage therefore needs its own recovery/export consideration. Periodically verify that attachment metadata still resolves to the expected private objects and that authorized downloads work after a recovery exercise.

## Customer information

Use the system for ordinary customer/contact and print-production information. Do not place payment-card numbers, passwords, medical records, government-ID images, or other regulated sensitive data in notes or artwork unless the organization has separately established the required compliance controls.
