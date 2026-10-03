# Print Order Manager Hardening + Web Roadmap

**Approved spec:** `docs/superpowers/specs/2026-10-02-print-order-manager-web-and-hardening-design.md`

Execution order:

1. `2026-10-02-01-hardening-and-migrations.md` — harden the current server/desktop system and introduce migrations.
2. `2026-10-02-02-web-api-and-sessions.md` — add shared services, browser sessions/CSRF, and REST APIs.
3. `2026-10-02-03-artwork-storage.md` — add private resumable artwork storage.
4. `2026-10-02-04-react-pwa.md` — build the complete online React/TypeScript PWA.
5. `2026-10-02-05-offline-deployment-acceptance.md` — add read-only outage support, CI/builds, deployment, and acceptance.

Each plan must end green and reviewed before the next begins.

## GitHub connector note

The connected GitHub integration currently returns `403 Resource not accessible by integration` when creating a branch, despite repository metadata reporting push/admin permission. Do not modify `main`. Before implementation, restore branch-write permission or use another supported writable GitHub connection.
