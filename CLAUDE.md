# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Tetra Host is a Cloud Industry branded multi-tenant hosting control panel. It orchestrates third-party
infrastructure providers — **Coolify** (sites/apps), **Mailcow** (mail), **Cloudflare** (DNS) — behind a
single admin/tenant surface.

The repo contains **two independent applications**:

- `app/` — the primary backend: Python **FastAPI** + **Jinja2/HTMX** server-rendered panel. This is the mature, deployed app (systemd → `uvicorn app.main:app` on `127.0.0.1:8088`).
- `apps/web/` — a separate **Next.js 16 / React 19** frontend (its own toolchain, tests, and `CLAUDE.md`/`AGENTS.md`). It talks to the FastAPI `/api/v1` contract. Treat it as a distinct project; see `apps/web/AGENTS.md` (note its warning: this Next.js has breaking changes vs. training data — read `node_modules/next/dist/docs/` before writing Next code).

## Commands

Python backend (run from repo root; uses a `.venv`):

```bash
pytest                          # full suite (pytest.ini sets pythonpath=.)
pytest tests/test_auth.py       # single file
pytest tests/test_auth.py::test_login_flow   # single test
ruff check .                    # lint (line-length 100)
uvicorn app.main:app --reload --port 8088     # run locally
```

Web frontend (from repo root, via root `package.json` proxy scripts, or inside `apps/web/`):

```bash
pnpm web:dev      # next dev
pnpm web:check    # lint + typecheck + vitest (run this before claiming web work is done)
pnpm web:test     # vitest run
```

Ops scripts: `scripts/install.sh` (systemd install), `scripts/bootstrap-admin.sh` (seed admin),
`scripts/check-production.sh` (run before restarting prod — it gates `systemd/tetra-host.service`).

## Tetra CLI (`tetra_cli/`)

`tetra` is a Python CLI (argparse + httpx, no new deps) that mirrors the dashboard against the same
`/api/v1` contract — per the charter's dashboard↔CLI parity rule. Run it without installing via
`python -m tetra_cli ...` or `scripts/tetra ...`; `pip install -e .` exposes the `tetra` command.

- `tetra login --url https://panel.cloud-industry.com` saves a token to `~/.config/tetra-host/config.json` (override with `TETRA_API_URL` / `TETRA_TOKEN` env).
- `tetra sites`, `tetra deploy <id> --follow` (streams build logs live), `tetra logs <site> <dep>`, `tetra deployments <id>`, `tetra dns zones|records|add|rm`, `tetra env list|set|rm`, `tetra dashboard`.
- It's a thin client over [tetra_cli/client.py](tetra_cli/client.py) (injectable httpx transport → tested in-process with `httpx.MockTransport`). **When you add a dashboard feature, add the matching CLI command.**

## Backend architecture (`app/`)

**Plugin-based modules.** Each feature is a self-contained module under `app/modules/<name>/` exposing a
`plugin.py` (a `PluginMeta` + `register(app)` that mounts an `APIRouter`). Modules are registered in order in
[app/modules/\_\_init\_\_.py](app/modules/__init__.py) `load_plugins()` and mounted via the global
`registry` ([app/plugins.py](app/plugins.py)). `PluginMeta` also drives the nav (`registry.nav_items()`).
**To add a feature, create a new module + plugin and add it to `load_plugins()`** — don't bolt routes onto
existing modules.

A module typically has: `routes.py` (thin handlers), `service.py` (business/provider logic), `plugin.py`,
and sometimes `schemas.py`. Current modules: `public`, `auth`, `dashboard`, `sites`, `databases`, `servers`,
`mail`, `dns`, `maintenance`, `admin`.

**Layering (enforce this).** Route handlers stay thin; all provider and domain logic lives in service
classes (`app/modules/*/service.py` and `app/services/`). Provider clients —
`app/services/{coolify,mailcow,cloudflare}.py` — go through the shared retrying HTTP helper
[app/services/http.py](app/services/http.py) (`request_json`, raises `ProviderAPIError`). Catch
`ProviderAPIError` in routes for user-facing errors.

**Two entry surfaces share the same services:**
- Server-rendered HTML/HTMX routes (the `app/modules/*` routers) — session-cookie auth, `require_admin`.
- A JSON contract API at `/api/v1` ([app/api/routes.py](app/api/routes.py), Pydantic models in `app/api/contracts.py`, token auth in `app/api/security.py`) — this is what `apps/web` consumes.

**App wiring** is in [app/main.py](app/main.py) `create_app()`: middleware (signed `SessionMiddleware`,
gzip, security headers, optional `TrustedHost`/HTTPS-redirect), plugin loading, and a `inject_core_context`
middleware that populates `request.state` (current admin, current tenant, `csrf_token`) for every request.
Health/readiness: `/health`, `/ready`.

**Config** is centralized in [app/config.py](app/config.py) (`Settings`, pydantic-settings, cached via
`get_settings()`). All env vars are documented in `.env.example`. Notable: `DATABASE_URL` is auto-normalized
to async drivers (`sqlite+aiosqlite` / `postgresql+asyncpg`); production refuses to boot with a default
`APP_SECRET`; provider write-actions are gated behind `ENABLE_PROVIDER_ACTIONS=false`.

**Persistence.** Async SQLAlchemy 2.0. Engine/session in [app/db/session.py](app/db/session.py) — use the
`get_db_session` FastAPI dependency in routes, or `session_scope()` for background/lifespan work. Models in
`app/models/` (`AdminUser`, `Tenant`, `TenantResource`, `AuditEvent`), re-exported from
`app/models/__init__.py`. `init_db()` (called in lifespan) creates tables; Alembic is a dependency but
migrations aren't the current workflow.

**Multi-tenancy is a hard requirement, not a feature flag.** Data access, API responses, and admin behavior
must isolate by tenant. The codebase is mid-migration from platform-global to tenant-aware — see
`app/services/tenants.py`, `app/services/tenant_resources.py`, and the `current_tenant_*` fields on
`request.state`. Treat any remaining platform-global shortcut as debt.

**Auth & CSRF.** Session-cookie admin auth ([app/modules/auth/service.py](app/modules/auth/service.py),
`ensure_bootstrap_admin` seeds from `ADMIN_BOOTSTRAP_*`). Protect routes with `require_admin` from
`app.routes`. **All state-changing form POSTs must validate CSRF** via `verify_csrf_token`
(`app/routes/deps.py`); the token is rendered into forms and read back from the session.

## Tests

`pytest` against FastAPI `TestClient` (`tests/conftest.py`). The fixture spins up a throwaway SQLite DB
(`data/test_tetra_host.db`, deleted around each test) and sets test env vars before importing the app, so
tests run with no external providers. `extract_csrf_token(html)` helper exists for exercising CSRF-protected
form flows.

## Conventions

- Keep handlers thin; put logic in services. Add/extend a module + plugin rather than fattening `main.py`.
- Typed boundaries: Pydantic contracts for the JSON API, explicit service method signatures.
- When adding provider calls, route them through `app/services/http.py` and surface `ProviderAPIError`.
- `.torsor/` markdown is project memory/architectural intent (the `torsor-helper` MCP server reads it); keep it accurate when architecture changes. `AGENTS.md` is generated from it.
