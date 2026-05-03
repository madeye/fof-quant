# Production deployment

> Replace `<server>`, `<domain>`, and `<your-email>` below with your own host, public domain, and contact email.

Single-server deployment of the dashboard behind nginx + Let's Encrypt + Cloudflare.

## Layout

| Component | Where | Bind |
|---|---|---|
| FastAPI service | `fof-api.service` (systemd, user `fof`) | `127.0.0.1:8001` |
| Next.js service | `fof-web.service` (systemd, user `fof`) | `127.0.0.1:3001` |
| nginx site | `/etc/nginx/sites-available/<domain>` | `:443` (TLS) → `127.0.0.1:3001` |
| Code | `/home/fof/app/` (rsync target) | — |
| Run registry | `/home/fof/app/runs/runs.db` (SQLite) | — |

## First-time setup

Run from a workstation with SSH access to `root@<server>`:

```bash
# 1. Server prep
ssh root@<server> 'useradd -m -s /bin/bash fof'
ssh root@<server> 'sudo -u fof bash -lc "curl -LsSf https://astral.sh/uv/install.sh | sh"'
ssh root@<server> 'mkdir -p /home/fof/app && chown fof:fof /home/fof/app'

# 2. Code transfer (run from the repo root locally)
rsync -az \
  --exclude='.git' --exclude='node_modules' --exclude='.next' --exclude='.venv' \
  --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.mypy_cache' --exclude='.ruff_cache' \
  --exclude='.env' --exclude='.env.local' \
  --exclude='runs/' --exclude='cache/csi300/' --exclude='cache/tushare/' \
  --exclude='reports/csi300/' --exclude='.DS_Store' --exclude='.claude/' \
  ./ root@<server>:/home/fof/app/
ssh root@<server> 'chown -R fof:fof /home/fof/app'

# 3. Build
ssh root@<server> 'sudo -u fof bash -lc "cd /home/fof/app && ~/.local/bin/uv sync --extra web"'
ssh root@<server> 'sudo -u fof bash -lc "cd /home/fof/app/web && bun install --frozen-lockfile && bun run build"'

# 4. Production env (the dashboard secret + OAuth credentials)
ssh root@<server> "cat > /home/fof/app/web/.env.local <<'EOF'
AUTH_SECRET=<openssl rand -base64 32>
AUTH_URL=https://<domain>
AUTH_GOOGLE_ID=<client id>
AUTH_GOOGLE_SECRET=<client secret>
ALLOWED_USERS=<your-email>
FOF_API_BASE=http://127.0.0.1:8001
EOF
chown fof:fof /home/fof/app/web/.env.local && chmod 600 /home/fof/app/web/.env.local"

# 5. systemd units
scp deploy/fof-api.service deploy/fof-web.service root@<server>:/etc/systemd/system/
ssh root@<server> 'mkdir -p /home/fof/app/runs && chown fof:fof /home/fof/app/runs
systemctl daemon-reload
systemctl enable --now fof-api fof-web'

# 6. nginx site (HTTP only — certbot rewrites with HTTPS in step 7)
scp deploy/site.nginx root@<server>:/etc/nginx/sites-available/<domain>
ssh root@<server> 'ln -sf /etc/nginx/sites-available/<domain> /etc/nginx/sites-enabled/ && nginx -t && systemctl reload nginx'

# 7. Let's Encrypt — Cloudflare must be DNS-only (grey cloud) for <domain> during this step.
ssh root@<server> 'certbot --nginx -d <domain> --non-interactive --agree-tos -m <your-email> --redirect'
# Then re-enable Cloudflare proxy (orange cloud) with SSL mode = Full.
```

The deploy/site.nginx file in this repo is the post-certbot version (with both HTTP→HTTPS redirect and the SSL block). If you start from scratch, `certbot --nginx` will mutate a plain HTTP site into this layout automatically; ship the file in step 6 only as a starting reference.

## Google OAuth

Add `https://<domain>/api/auth/callback/google` to the OAuth client's **Authorized redirect URIs** (Google Cloud Console → APIs & Services → Credentials → that client). The same client can serve both localhost dev and prod redirect URIs.

## Updating

```bash
# rsync new code, then:
ssh root@<server> 'sudo -u fof bash -lc "cd /home/fof/app && ~/.local/bin/uv sync --extra web"'
ssh root@<server> 'sudo -u fof bash -lc "cd /home/fof/app/web && bun install --frozen-lockfile && bun run build"'
ssh root@<server> 'systemctl restart fof-api fof-web'
```

## Logs

```bash
journalctl -fu fof-api
journalctl -fu fof-web
tail -f /var/log/nginx/access.log
```

## Notes / gotchas

- The FastAPI service binds to `127.0.0.1` only and is not behind any auth gate. The Next.js middleware (`web/middleware.ts` + Auth.js) is the access boundary; do not expose `:8001` to the network.
- The dashboard reads from `cache/broad_index/` and `reports/broad_index/`. Keep those directories on the server in sync via rsync, or schedule a `data refresh` job (requires `TUSHARE_TOKEN` in a server-side `.env`).
- `runs/runs.db` is the SQLite registry; it stores run metadata only. Delete to reset; artifacts under `reports/<run_id>/` survive.
- Cloudflare proxy interferes with Let's Encrypt's HTTP-01 challenge; switch the DNS record to **DNS only** (grey cloud) before each `certbot renew`. Auto-renewal via `certbot.timer` will fail otherwise — until that's solved, plan for manual renewal every 90 days.
