# Architecture

Tetra Host is a native Python hosting panel with a small stable core and plugin-based modules.

## Core responsibilities

- App boot (`app/main.py`)
- Settings (`app/config.py`)
- Database boot (`app/db.py`)
- Tenant/user/project models (`app/models.py`)
- Session/auth utilities (`app/security.py`)
- Plugin registry (`app/plugins.py`)
- Template/theme loader (`app/templating.py`)
- Static files and shared layout

The core should stay boring and stable. Hosting functionality lives in modules.

## Plugin/module contract

Each plugin provides:

```python
class SitesPlugin:
    meta = PluginMeta(
        name="sites",
        label="Sites",
        description="Coolify-backed site management",
        nav_label="Sites",
        nav_href="/sites",
    )

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
```

Module layout:

```text
app/modules/<plugin>/
├── __init__.py
├── plugin.py      # metadata + register(app)
├── routes.py      # FastAPI router
├── schemas.py     # optional pydantic schemas
├── service.py     # optional domain service
└── templates/     # optional module-local later
```

## Template/skin system

Template resolution order:

1. `TEMPLATE_SEARCH_PATH` from `.env` (colon separated override paths)
2. `app/themes/<THEME>/templates`
3. `app/templates`

Default theme: `cloud-industry`.

This allows customer/brand skins without changing route code.

## Planned plugins

- `sites`: Coolify API, apps, deployments, logs, domains, SSL
- `mail`: Mailcow API, mailboxes, aliases, domain DKIM/SPF/DMARC hints. Mailcow runs outside Coolify as a native Docker Compose stack because it owns SMTP/IMAP ports and has its own ACME/proxy assumptions.
- `dns`: Cloudflare DNS zones and records
- `admin`: tenants, users, plans, audit logs
- `billing`: optional Stripe/manual invoices
- `support`: tickets/requests

## Design rules

- No business logic in templates.
- No direct provider API calls from routes; use services.
- Every provider integration must be replaceable.
- Plugins own their routes and UI; core only loads them.
- Native install first; Docker optional later.
