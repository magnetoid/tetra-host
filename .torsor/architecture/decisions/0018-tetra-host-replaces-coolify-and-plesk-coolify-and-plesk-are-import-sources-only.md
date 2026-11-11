---
type: decision
status: accepted
tags:
- adr
links:
- 0017-tetra-engine-is-the-deploy-backend-coolify-is-migrated-off-roadmap-2026-11
- 0007-platform-is-modular-and-plugin-based
- 0012-mcp-server-is-read-only-by-default-writes-double-gated
created: '2026-11-11T00:00:00'
updated: '2026-11-11T00:00:00'
rules:
- id: tetra-coolify-import-source-only
  description: Coolify is an import source only. Never add panel, API, CLI or MCP features that read
    or change apps through Coolify; the only Coolify code is the importer (app/modules/importers/) and
    its read-only coolify_source client.
  severity: warn
---

# ADR 0018: Tetra Host replaces Coolify and Plesk; Coolify and Plesk are import sources only

## Context
ADR 0017 made the Tetra Engine the deploy backend but kept Coolify as a transitional `CoolifyDriver`.
The panel still listed, deployed, configured and logged Coolify apps (four plugin modules, about 50
routes, an 1100-line client, CLI and MCP commands), and the workspace hierarchy indexed Coolify apps
next to engine stacks. On 2026-11-11 the owner set the product direction: Tetra Host is an open-source
hosting panel that replaces Coolify + Plesk, so managing apps through Coolify is not a feature to keep.
The Coolify → engine importer already moves apps across with a staged, reversible cutover.

## Decision
1. **Amends ADR 0017 decision 1.** There is no `CoolifyDriver` stage: the panel does not manage Coolify
   apps at all. Coolify (and later Plesk) is only an **import source**.
2. The `projects`, `servers`, `databases` and `maintenance` modules, every `/api/v1/projects*` and
   `/api/v1/databases*` route, the Coolify GraphQL queries and the Coolify CLI/MCP commands are removed.
   Analytics (Umami) and errors (GlitchTip) move to engine apps at `/api/v1/apps/{project}/…`.
3. The only Coolify code left is the importer (`app/modules/importers/`) with a read-only client
   (`coolify_source.py`) that reads one application's metadata; compose, `.env` and volumes come from
   the Coolify data directory on the host. `COOLIFY_URL`, `COOLIFY_TOKEN` and `COOLIFY_DATA_DIR` are
   importer-only settings.
4. The workspace hierarchy indexes engine stacks only (git deploys, marketplace installs, imports,
   previews) and prunes rows whose stack is gone. Migration `0006_drop_coolify_rows` deletes
   `tenant_resources` with provider `coolify` and `apps` with driver `coolify`.
5. Features Coolify provided that the engine lacks — managed databases (provision, backups), app
   volumes, restart, cancel deploy, exec, build-settings editing, server inventory, the maintenance page —
   are removed now and rebuilt on the engine as their own roadmap items.

## Consequences
- Apps not yet imported keep running in Coolify but are not visible in the panel; the operator manages
  them in Coolify until `tetra import` moves them.
- The panel temporarily lacks managed databases, volumes, restart, cancel and exec.
- `tetra projects`, `deploy`, `deployments`, `logs`, `runtime-logs`, `env`, `volumes`, `update-app` and
  `databases` are gone; the engine equivalents are `tetra deploys …`, `tetra deploys env …` and
  `tetra apps logs`. `tetra analytics|errors|ai explain-error` take an engine app name.
- `tetra-engine-is-the-backend` (ADR 0017) is tightened by `tetra-coolify-import-source-only`.
- `app/services/app_catalog.py` and `edge.py` still read Coolify's open-source template format
  (Apache-2.0); that is catalog data, not the integration.
