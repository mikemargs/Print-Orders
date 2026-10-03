# Production Acceptance Checklist

Record the date, tester, environment, and result for every item. A failed item blocks production rollout unless the risk is explicitly accepted by the project owner.

## Automated CI

- [ ] GitHub Application CI is green on the release commit.
- [ ] Ruff passes with no unresolved errors.
- [ ] Python test suite passes.
- [ ] PostgreSQL migration from an empty database passes.
- [ ] Frontend typecheck, unit tests, lint, and production build pass.
- [ ] Playwright desktop and phone smoke tests pass.
- [ ] Production Docker image builds successfully.
- [ ] Windows installer workflow produces `PrintOrderManager-MultiStore-Setup.exe`.

## Staging — Render + Supabase

- [ ] `/api/health` reports healthy with the staging Supabase database available.
- [ ] Company login and employee PIN login succeed over HTTPS.
- [ ] Browser session cookie is Secure/HttpOnly and no bearer token appears in browser storage.
- [ ] Employee, Supervisor, and Administrator menus/permissions match their roles.
- [ ] Store-limited employee cannot mutate another store's order.
- [ ] Administrator can work across all configured stores.
- [ ] Final active administrator cannot be demoted or disabled.
- [ ] Customer create/edit/delete works and stale edits produce an explicit conflict.
- [ ] Work-order create/edit/status/line items/totals/print ticket work.
- [ ] Web changes appear in the Windows desktop after synchronization.
- [ ] Desktop changes appear in the web application.

## Browser outage

- [ ] Load representative customers and orders while online.
- [ ] Disconnect the browser device from the network.
- [ ] Offline banner appears with last-sync information.
- [ ] Cached orders and customers can be listed/opened read-only.
- [ ] New/edit/delete/admin/report/upload actions are unavailable offline.
- [ ] Reload the installed PWA while still offline and confirm cached read access remains available.
- [ ] Sign out during an outage; confirm the workstation does not silently restore the prior session when connectivity returns.

## Artwork

- [ ] Supabase bucket is private.
- [ ] Service-role key is present only in server-side environment configuration.
- [ ] Upload/download/delete a normal artwork file.
- [ ] Upload a representative large file near the expected upper range.
- [ ] Interrupt a large TUS upload and confirm it resumes rather than restarting from zero.
- [ ] Unauthorized/cross-store user cannot obtain the attachment or a signed download URL.
- [ ] Files over `MAX_UPLOAD_BYTES` and blocked executable MIME types/extensions are rejected.

## Desktop / legacy rollout

- [ ] Install the Actions-built Windows installer on a clean Windows workstation.
- [ ] Company token is absent from `client_config.json` and stored through Windows Credential Manager.
- [ ] Complete an online employee PIN login, disconnect, and verify approved offline desktop behavior.
- [ ] Change that employee's PIN or disable the employee, reconnect once, then confirm stale offline credentials no longer work.
- [ ] Back up each legacy database before import.
- [ ] Import one store at a time and compare customer/order counts and representative totals/dates/notes.
- [ ] Confirm desktop offline changes synchronize once after reconnect without duplicates.

## Recovery

- [ ] Take a staging database backup/export.
- [ ] Restore it into a separate non-production database.
- [ ] Run migrations and `/api/health` against the restored database.
- [ ] Verify representative customers, orders, employees, and attachment metadata.
- [ ] Verify private Storage objects still match attachment metadata and authorized downloads work.

## Final sign-off

- [ ] Sayville workflow approved.
- [ ] Selden workflow approved.
- [ ] Mt. Sinai workflow approved.
- [ ] Legacy system placed read-only only after count comparison and user sign-off.
