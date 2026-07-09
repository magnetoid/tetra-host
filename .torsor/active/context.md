---
type: active-context
status: active
tags:
- active
links: []
created: '2026-07-09T23:28:48'
updated: '2026-07-09T23:28:48'
---

# Active Context

## Current focus
Building the reseller marketplace (Path A): tenants activate/resell third-party services via API/CLI, scoped by TenantResource, gated by ENABLE_PROVIDER_ACTIONS, fail-closed ownership. Cloudflare plans/services + OpenRouter AI models are shipped backend-only (dormant). Now building the console reseller UI. New governing rule: tetra-clean-simple-core (ADR 0007) — keep the core minimal, grow by plugins.

## Open questions
Reseller still needs: console + panel UIs (console UI now in progress), a billing/markup model (how Tetra bills tenants and pays each provider — ties into the existing plans/billing), a reseller ADR, and deployment. Cloudflare activate endpoints trigger real billable plan changes, so they ship WITH the UI + billing model, not before. OpenRouter dormant until OPENROUTER_PROVISIONING_KEY set. Audit-log console/panel viewers still pending (backend shipped 16ca396). Slice F impersonation still needs the view-as vs act-as decision.
