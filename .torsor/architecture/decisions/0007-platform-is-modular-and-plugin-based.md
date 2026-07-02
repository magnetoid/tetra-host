---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T04:11:48'
updated: '2026-07-02T04:11:48'
rules:
- id: platform-plugin-modular
  description: Add each new capability as a self-contained plugin under app/modules/<name>/
    (plugin.py with PluginMeta+register, service.py, routes.py), registered in load_plugins(),
    with matching /api/v1 contract + tetra CLI + console surface. Don't bolt features
    onto existing modules or app/main.py; wrap third-party tools behind a thin service
    in their owning plugin.
  severity: warn
---

# ADR 0007: Platform is modular and plugin-based

## Context
The charter already states features should ship as self-contained plugins, but it's prose, not a machine-enforceable rule. The user wants "modular, plugin-based" made an explicit torsor rule so the drift guard enforces it and every new capability is added as a plugin rather than bolted onto existing modules or main.py.

## Decision
Every backend capability ships as a self-contained plugin under app/modules/<name>/ — a plugin.py exposing PluginMeta + register(app) that mounts an APIRouter, registered in app/modules/__init__.py load_plugins(), with its own service.py (business/provider logic behind a thin boundary), routes.py (thin handlers), and optional schemas.py. Third-party/OSS tools are wrapped behind a thin service inside their owning plugin. Matching surfaces stay in parity: the /api/v1 contract (app/api/contracts.py), the tetra CLI verbs, and the console. Never bolt new features onto existing modules or fatten app/main.py — so the platform stays composable, independently testable, and removable. Adding a new capability = a new module + plugin. This applies to the frontend too: console features are self-contained under apps/web with their own components/route segments.

## Consequences
Positive: composable, independently testable/removable capabilities; clear ownership; no god-modules. Trade-off: some boilerplate per plugin (plugin.py + service + routes + contract + CLI + console), and cross-cutting concerns must be shared via app/services/ rather than duplicated. Note: some current surfaces (e.g. the centralized /api/v1 in app/api/routes.py) predate strict per-plugin routers; treat consolidating those as debt, not a reason to bypass the rule for new work.
