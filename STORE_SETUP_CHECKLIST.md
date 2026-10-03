# Store Setup Checklist

Use this checklist for Sayville (#5127), Selden (#5345), and Mt. Sinai (#3167).

## Production web access

- [ ] Render production URL loads over HTTPS.
- [ ] `/api/health` returns healthy.
- [ ] Company code/password works.
- [ ] Each employee can select only appropriate store access (admins remain company-wide).
- [ ] Employee, Supervisor, and Administrator navigation/permissions are correct.
- [ ] Work order create/edit/print works from a desktop browser.
- [ ] Responsive work-order workflow is usable on a phone/tablet.
- [ ] A representative large artwork file uploads and can be downloaded by an authorized employee.
- [ ] Browser outage shows cached orders read-only and disables writes.

## Windows desktop

- [ ] Install the current Actions-built installer.
- [ ] Connect to the production HTTPS URL.
- [ ] Select the correct local store.
- [ ] Complete an online employee PIN login.
- [ ] Confirm offline desktop sign-in works only after a successful online login.
- [ ] Create an offline test order, reconnect, and confirm it synchronizes once.
- [ ] Confirm the same order appears in the web application.

## Legacy migration

- [ ] Back up the old local database.
- [ ] Import only once for this store.
- [ ] Allow synchronization to finish.
- [ ] Compare customer counts and work-order counts.
- [ ] Spot-check totals, due dates, notes, and completed/active status.
- [ ] Mark the legacy application read-only after sign-off.
