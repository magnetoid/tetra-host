# Tetra Host

Tetra Host (Cloud Industry / **Tetra AI Cloud**) is an open-source, multi-tenant hosting
platform: a Vercel-style console over best-in-class open-source infrastructure. It orchestrates
**Coolify** (apps/sites), **Cloudflare** (DNS), **Mailcow** (mail), **Hetzner Cloud** (compute),
plus **Umami**/**GlitchTip** observability — behind one control plane, one web console, one CLI,
and one MCP surface for AI agents.

## What's in this repo

| Path | What it is |
| --- | --- |
| `app/` | The control plane — Python FastAPI. Plugin-modular features (`app/modules/*`), provider clients (`app/services/*`), JSON contract at `/api/v1`, plus a legacy server-rendered admin panel. |
| `apps/web/` | The customer console — Next.js 16 / React 19 / Tailwind v4, shadcn-style design system. Talks only to `/api/v1`. See [apps/web/README.md](apps/web/README.md). |
| `tetra_cli/` | `tetra` — CLI with dashboard parity (`tetra deploy`, `tetra dns`, `tetra env`, …) and `tetra mcp serve`, an MCP server exposing the same contract to AI agents. |
| `scripts/` | Install, bootstrap-admin, and production-gate scripts. |
| `docs/` | Architecture, deployment, and operations notes. `.torsor/` holds architectural intent. |

## Run it locally

Backend (Python ≥ 3.11):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                 # defaults work for local dev (SQLite, no providers)
uvicorn app.main:app --reload --port 8088
bash scripts/bootstrap-admin.sh      # seed an admin account
```

Console (Node 22+, pnpm):

```bash
cd apps/web
pnpm install
cp .env.example .env.local
pnpm dev                             # http://127.0.0.1:3000
```

Without provider credentials the console runs in a degraded-but-honest mode: pages render and
tell you which sources are unavailable.

## Checks

```bash
pytest             # backend suite (throwaway SQLite, no providers needed)
ruff check .       # backend lint
pnpm web:check     # console lint + typecheck + vitest (root proxy script)
```

CI runs all of the above on every push/PR (`.github/workflows/ci.yml`).

## Production install (native, systemd)

```bash
sudo bash scripts/install.sh
sudo ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='***' bash scripts/bootstrap-admin.sh
```

- The service listens on `127.0.0.1:8088`; put nginx (or similar) in front for TLS.
- Set a real `APP_SECRET` (production refuses to boot with the default) and prefer
  `DATABASE_URL=postgresql://…`.
- `scripts/check-production.sh` gates restarts; `/health` is liveness, `/ready` probes the DB.
- Set `SESSION_HTTPS_ONLY=true`, `FORCE_HTTPS_REDIRECT=true` behind TLS, and enable
  `ENABLE_PROVIDER_ACTIONS=true` only after validating provider credentials.
- All configuration is documented in [.env.example](.env.example) (backend) and
  [apps/web/.env.example](apps/web/.env.example) (console).

## Architecture in one paragraph

Every feature is a plugin module (`app/modules/<name>/plugin.py` + `service.py`) mounted by a
registry; route handlers stay thin and all provider/domain logic lives in service classes that
call out through one retrying HTTP helper (`app/services/http.py`). Three surfaces share those
services: the server-rendered admin panel, the `/api/v1` JSON contract (typed with Pydantic in
`app/api/contracts.py`), and — consuming that contract — the Next.js console, the `tetra` CLI,
and the MCP server. Dashboard ↔ CLI ↔ MCP parity is a charter rule; multi-tenant isolation is a
hard requirement, not a feature flag.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), and
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Cloud Industry.
