---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-03T01:50:00'
updated: '2026-07-03T01:50:00'
rules:
- id: tetra-analytics-umami-not-matomo
  rule: Per-project web analytics integrate with the self-hosted Umami sidecar via
    app/services/umami.py; do not add Matomo or third-party SaaS analytics (GA, Plausible
    Cloud) to the tenant surface.
- id: tetra-analytics-config-gated
  rule: Analytics/error-tracking features must degrade gracefully when UMAMI_URL/GLITCHTIP_URL
    are unset (show a connect state), so the platform remains fully functional without
    the sidecars.
---

# ADR 0011: Analytics stack: Umami for tenant web analytics, own docker-stats for compute, ClickHouse product analytics deferred

## Context
The platform needs three distinct kinds of analytics: (1) per-project web analytics for tenants (a Vercel-Analytics-style Metrics tab), (2) internal compute stats (CPU/mem/net per app, Vercel "Usage"-style), and (3) deep product/event analytics. Matomo vs Umami was evaluated for (1): Matomo is PHP/MySQL, heavyweight, cookie-consent-encumbered, and not API-first for programmatic per-project provisioning; Umami v2 is MIT, Next.js/Postgres, cookieless (no consent banner for basic use), and its REST API lets Tetra find-or-create a website per project and pull stats server-side. An Umami sidecar is already live on the prod box (umami.apps.cloud-industry.com via the tetra-edge Caddy) with the config-gated analytics plugin (app/modules/analytics) wired to it, alongside GlitchTip for the Errors tab. Compute stats already ship via our own docker-stats pipeline (app/services/compute.py + Tremor Compute panel).

## Decision
Tenant web analytics = self-hosted Umami (one Umami "website" per Tetra project, provisioned via API; tracking snippet surfaced in the Metrics tab). Error tracking = self-hosted GlitchTip (Sentry-API-compatible). Internal compute metrics = own docker-stats sampling (no third-party dependency), with cAdvisor + VictoriaMetrics as the later history tier. Matomo is rejected. Deep product/event analytics (PostHog or OpenPanel on ClickHouse) is deliberately deferred to the scale phase — revisit only when a tenant-facing event-analytics product is on the roadmap, since ClickHouse is a heavy operational commitment on the constrained shared box.

## Consequences
The Metrics/Errors tabs stay config-gated (UMAMI_URL / GLITCHTIP_URL empty = clean "connect" state), so open-source installs work without the sidecars. All analytics integrations must go through thin service clients (app/services/umami.py, glitchtip.py) using the shared retrying HTTP helper. No ClickHouse operational burden today; the cost is that event-level product analytics (funnels, retention) are unavailable until the deferred decision is revisited. Compute history is bounded by live docker-stats sampling until the cAdvisor+VictoriaMetrics tier lands.
