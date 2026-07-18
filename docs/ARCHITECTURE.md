# Architecture

Tetra Host is a multi-tenant hosting control plane with a small FastAPI core, plugin-based HTML surfaces,
and a contract-first `/api/v1` layer shared by the Next.js console, `tetra` CLI, and MCP server.

## Core responsibilities

- App boot and middleware wiring (`app/main.py`)
- Settings and production safety validation (`app/config.py`)
- Database engine/session boot plus legacy schema upgrades (`app/db/session.py`)
- SQLAlchemy models (`app/models/`)
- Plugin registry and navigation metadata (`app/plugins.py`)
- Shared services, provider clients, and HTTP abstraction (`app/services/`)
- JSON API contracts and routes (`app/api/`)
- Templates, static files, and shared layout for the server-rendered panel

The core should stay boring and stable. Product capabilities live in modules and services.

## Plugin/module contract

Each plugin exposes metadata and mounts its own routes:

```python
class ProjectsPlugin:
    meta = PluginMeta(
        name="projects",
        label="Projects",
        description="Applications, deploys, logs, and domains",
        nav_label="Projects",
        nav_href="/projects",
    )

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
```

Module layout:

```text
app/modules/<plugin>/
├── __init__.py
├── plugin.py      # metadata + register(app)
├── routes.py      # FastAPI router / HTML handlers
├── schemas.py     # optional Pydantic schemas
├── service.py     # optional domain service
└── templates/     # optional module-local templates
```

Some domains are service-only rather than plugin-backed. Those modules expose reusable logic that is consumed
through existing plugins and the `/api/v1` contract.

## Runtime surfaces

- Server-rendered panel: plugin-owned HTML routes for operational admin workflows
- JSON API: typed `/api/v1` endpoints consumed by the web console, CLI, and MCP server
- GraphQL: a smaller query layer for flexible reads
- Next.js console: the modern customer-facing control panel in `apps/web/`
- CLI / MCP: automation and AI-agent operability over the same backend contract

## Current plugins and service domains

Registered plugins:

- `public`
- `auth`
- `dashboard`
- `projects`
- `databases`
- `servers`
- `mail`
- `dns`
- `domains`
- `maintenance`
- `plans`
- `account`
- `admin`

Service-only domains in active use include `apps`, `deploys`, `analytics`, `errors`, `reseller`, and `billing`.

## Template/skin system

Template resolution order:

1. `TEMPLATE_SEARCH_PATH` from `.env` (colon-separated override paths)
2. `app/themes/<THEME>/templates`
3. `app/templates`

Default theme: `cloud-industry`.

This allows customer/brand skins without changing route code.

## Design rules

- Keep route handlers thin; business logic belongs in services.
- Do not call provider APIs directly from routes; go through `app/services/`.
- Keep every provider integration replaceable.
- Let plugins own their routes and UI; core only loads them.
- Preserve dashboard, CLI, and MCP parity over the same API contract.
