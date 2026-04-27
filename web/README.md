# fof-quant dashboard (Phase 7 v1.1)

Read-only Next.js (App Router, TypeScript, ECharts) frontend for the
`fof-quant` run registry. Pairs with the FastAPI service at
`src/fof_quant/web/`.

## Develop

Two terminals:

```bash
# 1) start the API (CWD = repo root)
uv sync --extra web
uv run fof-quant web serve --reports-dir reports/

# 2) start the UI
pnpm --dir web install
pnpm --dir web dev
```

Visit <http://localhost:3000>.

`FOF_API_BASE` env var overrides the API base URL (default
`http://127.0.0.1:8000`).

## Auth (Google login)

The dashboard requires sign-in via Google. Configure once:

1. Copy `web/.env.example` to `web/.env.local`.
2. Generate a session secret: `openssl rand -base64 32` → `AUTH_SECRET`.
3. In Google Cloud Console → APIs & Services → Credentials, create an OAuth
   2.0 Client ID (Application type: Web application). Add the redirect URI
   `http://localhost:3000/api/auth/callback/google`. Paste the client ID
   and secret into `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET`.
4. Add allowed Google accounts (comma-separated) to `ALLOWED_USERS`. The
   list is the allowlist — anyone outside it sees `AccessDenied` after the
   Google round-trip.

The FastAPI service stays loopback-only (`127.0.0.1:8000`) and is not
gated; the Next.js middleware is the access boundary, so don't expose
the API to the network.

## Pages

- `/` — run list with multi-select → Compare
- `/runs/[id]` — single-run dashboard (NAV chart, drawdown, metrics,
  allocation; for signal runs, target allocation + rebalance lines)
- `/compare?ids=a,b` — two strategies on one NAV chart, side-by-side
  metrics with Δ column, and allocation diff
