# Offline, Deployment, and Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web app installable/read-only offline, replace incorrect CI, build Windows artifacts, and verify a Render/Supabase rollout.

**Architecture:** Service worker caches the app shell; IndexedDB stores bounded read-only order/customer data. CI validates Python/PostgreSQL/frontend/Windows builds. Render serves FastAPI + compiled web assets; Supabase hosts PostgreSQL + private Storage.

**Tech Stack:** vite-plugin-pwa, Dexie/IndexedDB, Playwright, GitHub Actions, PyInstaller, Inno Setup, Render, Supabase.

**Spec:** `docs/superpowers/specs/2026-10-02-print-order-manager-web-and-hardening-design.md`

## Global Constraints

- Browser outage mode is read-only.
- Cached records show last-online timestamp.
- Artwork bytes are never cached.
- Production uses HTTPS.
- No credentials/customer data embedded in builds.
- Docs must match actual commands/files.

## Review Focus

- Going offline mid-navigation must disable write controls.
- Logout on shared devices must not leave usable session state.
- IndexedDB schema upgrades must migrate/reset safely.
- Failed Windows build must not publish installer artifact.
- DB outage must fail production health.

---

### Task 1: Add bounded IndexedDB read cache

**Files:** create `web/src/offline/db.ts`, `cache.ts`; modify data hooks; tests.

- [ ] Write failing cache read/write/version/reset tests.
- [ ] Implement Dexie schema and bounded cache.
- [ ] Confirm artwork bytes/signed URLs are excluded.
- [ ] Commit `feat: cache recent records for offline viewing`.

### Task 2: Read-only outage UX and installable PWA

**Files:** modify Vite config; create online-state provider; modify action/form components; add manifest/icons; tests.

- [ ] Write failing offline-control tests.
- [ ] Configure app-shell service worker caching.
- [ ] Implement offline banner + last-sync timestamp.
- [ ] Disable create/edit/delete/admin/upload while offline.
- [ ] Verify reload offline after one successful online load.
- [ ] Commit `feat: add read-only PWA outage mode`.

### Task 3: Serve compiled web app from FastAPI image

**Files:** modify `server/Dockerfile`, web/static routing, build scripts; smoke test.

- [ ] Write failing production static/deep-route test.
- [ ] Implement multi-stage web+server build.
- [ ] Ensure `/api/*` remains API-only.
- [ ] Verify deep route refresh and health endpoint.
- [ ] Commit `build: serve React PWA from FastAPI image`.

### Task 4: Replace GitHub Actions workflows

**Files:** delete `.github/workflows/python-publish.yml`; create `ci.yml`, `windows-installer.yml`.

- [ ] Implement Linux CI with PostgreSQL service, migrations, Python tests, Ruff, web tests/typecheck/build.
- [ ] Implement Windows PyInstaller + Inno Setup build.
- [ ] Validate workflow YAML.
- [ ] Once pushed, inspect real workflow results before claiming success.
- [ ] Commit `ci: add application and Windows build pipelines`.

### Task 5: Correct environment/deployment docs

**Files:** create/update `.env.example`; modify deployment/security/setup/readme docs.

- [ ] Cross-check every documented filename/command.
- [ ] Add exact Render/Supabase environment setup.
- [ ] Add migration, backup, restore, rollback, bucket configuration.
- [ ] Commit `docs: add production web deployment guide`.

### Task 6: End-to-end browser smoke tests

**Files:** create Playwright config/e2e specs; test fixtures.

- [ ] Add sign-in/customer/order tests.
- [ ] Add artwork-flow test using fake/local storage adapter.
- [ ] Add phone viewport test.
- [ ] Add offline cached-view test.
- [ ] Run Playwright suite.
- [ ] Commit `test: add browser end-to-end coverage`.

### Task 7: Production acceptance rehearsal

**Files:** modify `VALIDATION.md`; create `docs/PRODUCTION_ACCEPTANCE.md`.

- [ ] Deploy staging Render/Supabase.
- [ ] Run full Python/frontend/E2E suites.
- [ ] Run Windows installer workflow/install smoke test.
- [ ] Run three-store authorization and desktop disconnect/reconnect tests.
- [ ] Run database restore exercise.
- [ ] Run representative 250 MB resumable upload/resume.
- [ ] Verify web<->desktop propagation.
- [ ] Record actual results and unresolved risks.
- [ ] Commit `docs: record production acceptance results`.
