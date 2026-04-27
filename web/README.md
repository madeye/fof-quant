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

## Pages

- `/` — run list with multi-select → Compare
- `/runs/[id]` — single-run dashboard (NAV chart, drawdown, metrics,
  allocation; for signal runs, target allocation + rebalance lines)
- `/compare?ids=a,b` — two strategies on one NAV chart, side-by-side
  metrics with Δ column, and allocation diff
