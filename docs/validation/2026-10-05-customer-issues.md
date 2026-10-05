# Customer Issues validation and decisions

## Local verification

- `python -m unittest discover -s tests -v`: 92 passed.
- `python -m ruff check .`: passed.
- `npm test --prefix web`: 28 passed.
- Frontend typecheck, ESLint and production build: passed.
- Full Playwright suite against a migrated SQLite test database: 4 passed. Used official Chromium headless 140 with a temporary local executable configuration because the newest browser download was truncated in this environment.
- Existing cached-order outage and offline sign-out journeys passed.
- New journey covered customer/case creation, contact logging and follow-up, resolution/reopening, employee store restrictions, phone layout and sign-out isolation.

## Review findings resolved

A fresh whole-branch reviewer found three material issues and no minor findings.
Secondary actions now preserve unrelated dirty fields and resolution drafts; a
refresh that overlaps another employee's edit requires review before resubmission.
Uncertain response/body failures retain the identical communication operation ID
and payload. Tests reproduced failures before fixes, then passed.

Rollback instructions now require a prior-code build retaining deployed migration
history. An isolated rehearsal reproduced failure of unmodified prior startup on
revision 0007, then verified successful prior-code migration startup with the
current migrations retained and customer/case/communication data preserved.

## Implementation decisions and practical limits

- Used a dedicated feature checkout rather than a second worktree: no shared user
  files existed in the fresh clone. Concurrent edits in that checkout would reduce
  isolation.
- Browser integration tests were written after unit/API failure-first cycles rather
  than deleting already-tested implementation to recreate a failing browser probe.
  This gives weaker browser mutation proof, while actual integration defects were
  caught and corrected.
- Existing work-order reassignment does not automatically reconcile historical case
  links. Case edits validate linked customer/store/order ownership; a moved order
  can temporarily retain a historical link with a different current customer/store.
- Email delivery, reminders, attachments and offline case editing remain excluded
  by the approved manual-online scope; employees use existing external tools.
- Local checks do not prove production PostgreSQL, Docker or deployment results.
  GitHub CI must pass before merge; production remains unchanged by this branch.
