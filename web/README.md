# Print Order Manager Web

React/TypeScript browser client for the Print Order Manager API.

## Development

```bash
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000` during development. Browser authentication uses secure HttpOnly cookies; JavaScript stores only the non-secret CSRF token in memory.

## Verification

```bash
npm test
npm run typecheck
npm run lint
npm run build
```

The production build is written to `web/dist` and is served by FastAPI's SPA fallback after the deployment image copies it into the configured `WEB_DIST_DIR`.
