# Tetra AI Cloud — Platform Strategy & Structure

> Deep-dive synthesis (2026-07-02). Evidence: the 12-stream research in
> `docs/research/2026-07-01-tetra-ai-cloud/` and ADR 0004. This doc states the
> positioning, the whole-environment structure, and the build thesis.

## Positioning: between Vercel and a hosting platform

Vercel sells **developer experience on ephemeral compute** (push → preview → promote,
zero servers). Classic hosts (Plesk/cPanel) sell **durable tenancy** (domains, mail,
databases, files that live for years). Nobody credibly does both. Tetra's bet:

**One tenant-aware control plane where a `git push` and a mailbox are the same product.**

Concretely, a Tetra tenant gets:
- **Vercel side** — push-to-deploy (HMAC webhooks ✅), live build logs (SSE ✅),
  env/secrets encrypted at rest (✅), instant rollback (✅), per-app compute stats (✅),
  preview envs (Coolify native; surfacing planned).
- **Hosting side** — one-click apps/WordPress (✅ catalog), managed databases (✅ via
  Coolify), DNS (✅ Cloudflare), custom domains (this slice), mail (Phase 2: dedicated
  Mailcow + ESP relay), plans/quotas/approval (✅).

The connective tissue neither world has: **hard multi-tenancy** (fail-closed
`TenantResourceFilter`, quotas → 402, audit) and **dashboard ↔ CLI ↔ (soon) MCP parity**
over one `/api/v1` contract.

## Environment structure (layers)

```
┌────────────────────────────────────────────────────────────────────┐
│ SURFACES     Next.js console · Jinja panel · tetra CLI · MCP (P4)  │
├────────────────────────────────────────────────────────────────────┤
│ CONTROL      FastAPI /api/v1 (contracts.py) · plugin modules       │
│ PLANE        (ADR 0007) · tenants/plans/quotas · audit · secrets   │
├──────────────────────────┬─────────────────────────────────────────┤
│ DEPLOY BACKENDS          │ PROVIDER APIs (via services/http.py)    │
│ · Tetra Engine (native): │ · Coolify /api/v1 (apps, DBs, previews) │
│   builder (Dockerfile/   │ · Cloudflare (DNS, later: for-SaaS)     │
│   Nixpacks→Railpack),    │ · Mailcow (P2, dedicated host)          │
│   docker_engine, edge    │ · Hetzner hcloud (P3, 1 project/tenant) │
├──────────────────────────┴─────────────────────────────────────────┤
│ EDGE         Caddy (docker-proxy, "tetra" labels) behind nginx     │
│              wildcard *.apps.* · custom domains via ask-endpoint    │
├────────────────────────────────────────────────────────────────────┤
│ DATA/RUNTIME Docker (shared kernel, trusted tenants, cgroup caps    │
│              pending) · SQLite→Postgres · per-tenant networks       │
└────────────────────────────────────────────────────────────────────┘
```

**Two deploy backends by design.** Coolify (Apache-2.0, white-label-safe) carries the
heavy catalog + managed DBs + PR previews; the **Tetra Engine** is the sovereign path —
zero-Coolify git→image→edge — and the escape hatch that keeps Coolify a replaceable
vendor (its constraints: team-scoped tenancy, 200 rpm, poll-not-events, moving API).

**Infra course (P3):** Hetzner hcloud directly for hot-path server ops (one Hetzner
project per tenant = isolation for free; hourly billing suits preview/burst compute);
OpenTofu/Pulumi only for multi-resource graphs; never Terraform (BSL).

## Ideas / differentiators worth building toward

1. **Domains as a first-class object** (this slice) — verify once, attach to any app,
   auto-DNS when the zone is already on the tenant's Cloudflare, on-demand TLS at the
   edge. Vercel-grade UX on hosting-grade ownership.
2. **MCP control plane (P4)** — dashboard↔CLI↔MCP parity makes Tetra the first small
   PaaS that agents can operate safely (reads open, writes human-gated).
3. **"Draft + approve" AI ops** — failed build → AI-drafted diagnosis from build log +
   GlitchTip/Umami context; human clicks apply. Production-validated zone, not hype.
4. **Migration as a product** (P5) — the Plesk manifest→build→cutover state machine,
   generalized: "move your site off any cPanel/Plesk host" is an acquisition funnel,
   not just our own 30-site chore.
5. **Compute honesty** — live per-container stats (✅) → cAdvisor+VictoriaMetrics
   history → metering (OpenMeter/Lago→Stripe). Bill what's measured, show what's billed.
6. **Golden paths over knobs** — one blessed way per job (deploy, domain, mailbox);
   escape hatches exist but are never the default UX.

## Sequencing (unchanged from ADR 0004, now with progress)

P0 foundation+rebrand ✅ → **P1 Vercel-DX** (SSE ✅, env/secrets ✅, webhooks ✅,
rollback ✅, compute ✅, **custom domains ← now**, previews surfacing) → P2 mail →
P3 Hetzner → P4 AI/MCP → P5 Plesk migration → P6 scale (gVisor tier, k3s option,
metering). Standing constraints: trusted-tenant-only until the gVisor tier ships;
disk pressure on the shared box is a real design input.
