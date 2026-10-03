# Artwork Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure private resumable artwork-file attachments without proxying large file bodies through FastAPI.

**Architecture:** FastAPI owns authorization/metadata; Supabase Storage owns bytes. Browser gets short-lived upload authorization, uploads directly with TUS, then finalizes metadata through FastAPI.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Supabase Storage HTTP API, private bucket, Uppy/TUS contract, fake storage adapter tests.

**Spec:** `docs/superpowers/specs/2026-10-02-print-order-manager-web-and-hardening-design.md`

## Global Constraints

- Private bucket only.
- Never expose service-role secret to browser.
- Normal files are 25–250 MB.
- FastAPI authorizes upload/download/delete.
- Artwork bytes are never part of offline browser cache.

## Review Focus

- Path traversal/object-key injection cannot escape company/order namespace.
- Finalize rejects objects not issued for the current order/session.
- Cross-company users cannot get signed downloads.
- Retry/resume does not duplicate active metadata.
- Oversize/disallowed content is rejected before authorization.

---

### Task 1: Attachment metadata and migration

**Files:** modify model module; create Alembic migration; test `tests/test_files.py`.

**Interfaces:** `ArtworkFile(id, company_id, work_order_id, object_key, original_filename, mime_type, size_bytes, uploaded_by, created_at, checksum, active)`.

- [ ] Write failing model/tenant/index tests.
- [ ] Verify failure.
- [ ] Add migration/model.
- [ ] Verify PostgreSQL migration and tests.
- [ ] Commit `feat: add artwork attachment metadata`.

### Task 2: Storage adapter

**Files:** create `server/app/storage/base.py`, `fake.py`, `supabase.py`, config; test `tests/test_storage.py`.

**Interfaces:** create upload authorization, verify uploaded object, create download URL, delete object.

- [ ] Write adapter contract tests against fake.
- [ ] Verify failure.
- [ ] Implement fake adapter.
- [ ] Use Context7 at implementation time to confirm current Supabase signed/TUS API details.
- [ ] Implement Supabase adapter and ensure returned payload contains no service-role value.
- [ ] Commit `feat: add private storage adapter`.

### Task 3: Upload authorization and finalize

**Files:** create `services/files.py`, `routers/files.py`, `schemas/files.py`; test `tests/test_files.py`.

**Interfaces:** `POST /api/orders/{order_id}/files/upload-authorizations`; `POST /api/orders/{order_id}/files/finalize`. Object key is server generated.

- [ ] Write failing size/MIME/tenant/store/CSRF/duplicate-finalize tests.
- [ ] Verify failures.
- [ ] Implement authorization.
- [ ] Implement finalize after storage verification only.
- [ ] Verify and commit `feat: authorize and finalize artwork uploads`.

### Task 4: List/download/delete attachments

**Files:** modify file service/router/tests.

- [ ] Write failing role/tenant/download/delete tests.
- [ ] Verify failures.
- [ ] Implement list and short-lived signed download.
- [ ] Implement retry-safe delete/soft-delete behavior.
- [ ] Verify and commit `feat: manage artwork attachments`.

### Task 5: Storage configuration/docs

**Files:** create/update `server/.env.example`; modify deployment/security docs.

- [ ] Add missing-production-config tests.
- [ ] Document private bucket and size ceiling.
- [ ] Document storage recovery considerations.
- [ ] Run full server suite.
- [ ] Commit `docs: configure private artwork storage`.
