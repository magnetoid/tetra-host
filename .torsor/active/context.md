---
type: active-context
status: active
tags:
- active
links: []
created: '2026-07-09T23:28:48'
updated: '2026-11-10T00:00:00'
---

# Active Context

## Current focus
Roadmap 2026-11 (docs/architecture/roadmap.md, ADR 0017, ADR 0018): Tetra Engine is the deploy backend; the panel's Coolify integration is removed (2026-11-11), Coolify is an import source only. Phase 0 (hygiene: ruff rule set pinned, dead legacy files removed, OpenAPI contract snapshot) in progress; phase 1 (plugin kernel v2 + AuthContext, splitting app/api/routes.py per plugin, jobs first) next. Owner priority: move his own Plesk sites and Coolify apps onto the engine site by site (mtiosavljevic.com first), then the reseller layer. Deployed production is at 0a6773c (2026-11-10).

## Open questions
Reseller still needs: console + panel UIs (console UI now in progress), a billing/markup model (how Tetra bills tenants and pays each provider — ties into the existing plans/billing), a reseller ADR, and deployment. Cloudflare activate endpoints trigger real billable plan changes, so they ship WITH the UI + billing model, not before. OpenRouter dormant until OPENROUTER_PROVISIONING_KEY set. Audit-log console/panel viewers still pending (backend shipped 16ca396). Slice F impersonation still needs the view-as vs act-as decision.
