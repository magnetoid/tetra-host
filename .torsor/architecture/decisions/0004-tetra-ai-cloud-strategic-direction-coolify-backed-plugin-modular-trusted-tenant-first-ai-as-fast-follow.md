---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-01T23:02:18'
updated: '2026-07-01T23:02:18'
rules:
- id: tetra-tenancy-trusted-only
  description: Until a gVisor/microVM isolation tier ships, do NOT run untrusted/public-signup
    code on shared-kernel Docker; tenant containers must carry cgroup v2 hard limits
    (cpus+memory.max+pids.max+io.max).
  severity: warn
- id: tetra-coolify-version-pin
  description: Pin the Coolify version and regenerate API clients from its OpenAPI
    on upgrade; assume /api/v1 is versioned-but-moving with no deprecation policy.
  severity: info
- id: tetra-no-terraform-bsl
  description: For IaC in this commercial hosting product, use OpenTofu (MPL) or Pulumi,
    never Terraform (BSL); avoid Nomad (BUSL) as a backend.
  severity: warn
- id: tetra-mail-off-shared-host
  description: Self-hosted mail (Mailcow) runs on a dedicated host with per-tenant
    ESP relay for outbound; never co-locate it on the shared Plesk box or send outbound
    directly from fresh Hetzner IPs.
  severity: warn
---

# ADR 0004: Tetra AI Cloud strategic direction: Coolify-backed, plugin-modular, trusted-tenant-first, AI as fast-follow

## Context
The product is evolving from "Tetra Host" into "Tetra AI Cloud" — one open-source hosting control plane fusing Plesk (traditional web/mail/DNS for ~30 legacy sites to migrate later), Coolify (container deploys), Cloudflare (DNS/edge), and Vercel-grade DX. Backed by 12 parallel research streams (2026-07-01, preserved in docs/research/2026-07-01-tetra-ai-cloud/) plus a full codebase map. The codebase already has a Coolify-independent "Tetra Engine" (builder/docker_engine/app_catalog/edge), multi-tenancy scaffolding, /api/v1 + ~150 CLI verbs at parity, and a Next.js console. Four strategic forks were resolved with the user this session.

## Decision
Adopt the Tetra AI Cloud direction with these locked choices: (1) TENANCY = trusted/own-customers first — shared-kernel Docker + cgroup v2 hard limits (--cpus+memory.max+pids.max+io.max, not weight-only) + per-tenant Docker networks + patched runc (>=1.2.8/1.3.3); a gVisor/microVM isolation tier is deferred but the runtime seam stays clean. Do NOT accept untrusted public code on shared-kernel Docker until that tier ships. (2) BACKEND = stay on Coolify (Apache-2.0, safe to white-label, /api/v1 OpenAPI) as the deploy backend + keep the own Tetra Engine as the non-Coolify escape hatch; hold k3s as the future scale/hard-isolation lever; avoid Nomad (BUSL). Design around Coolify constraints: team=tenancy boundary (one team-scoped token per tenant), poll (no event bus), 200 req/min, TLS-via-FQDN, moving /api/v1 with no deprecation policy (version-pin + regen from OpenAPI). (3) FIRST FOCUS = finish the multi-tenant SaaS foundation (tenants-and-plans, quotas, signup/approval, fail-closed isolation) + Vercel-DX polish over Coolify (GitHub-App push-to-deploy, preview envs, registry-backed instant rollback, build-log SSE shim, custom-domain TLS via Caddy On-Demand `ask` endpoint or Cloudflare for SaaS, at-rest secret custody, Railpack as forward build default). (4) MAIL = dedicated Mailcow host + per-tenant ESP relay for outbound (Hetzner blocks port 25/465 by default; fresh-VPS IP reputation is poor) + auto DKIM/SPF/DMARC via existing Cloudflare integration. (5) OWN-INFRA = Hetzner via hcloud API through app/services/http.py (3,600 req/hr; one Hetzner project per tenant = free isolation); direct API for hot-path, Pulumi Automation API (or OpenTofu, never Terraform/BSL) reserved for multi-resource env graphs. (6) AI = fast-follow: a Tetra MCP server over /api/v1 (dashboard<->CLI<->MCP parity, human-gated writes, Code Mode pattern) + AI-assisted deploy/log debugging as "draft + approve", golden-paths-over-knobs. (7) PLESK MIGRATION of the 30 sites is a later phase via a `migrations` plugin (manifest->build->cutover state machine). Every capability ships as a self-contained plugin under app/modules/<name>/ with /api/v1 contract + tetra CLI verbs + console surface (charter rule). Phased program: P0 foundation+rebrand -> P1 Vercel-DX -> P2 mail -> P3 Hetzner -> P4 AI/MCP -> P5 Plesk migration -> P6 scale/hardening.

## Consequences
Positive: each phase is independently valuable and sellable; leverages what already exists (Tetra Engine, /api/v1, CLI parity) rather than rebuilding; the AI angle is production-validated (MCP + assisted ops), not vaporware; trusted-first keeps time-to-market low. Trade-offs/risks: Coolify coupling (moving API, 200 rpm, poll-not-events) — mitigated by version-pinning + the engine escape hatch; mail deliverability is an ops problem (PTR/reputation) not a software one; Plesk cutover has genuine footguns (same-domain mail loopback, DNSSEC-before-NS-change); this is a multi-quarter program that must ship slice-by-slice with review checkpoints. Trusted-only tenancy is a standing constraint until the gVisor tier is built. Re-verify before hard-coding: live Coolify OpenAPI (rollback/log endpoints, one-App-per-instance for many tenants), Hetzner port-25 unblock policy for multi-tenant + current pricing, Gmail/MS PTR hard-reject thresholds, Mailcow per-tenant delegation limits.
