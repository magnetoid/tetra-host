---
type: decision
status: accepted
tags:
- adr
links:
- 0004-tetra-ai-cloud-strategic-direction-coolify-backed-plugin-modular-trusted-tenant-first-ai-as-fast-follow
- 0007-platform-is-modular-and-plugin-based
- 0009-custom-domain-tls-cloudflare-for-saas-now-dedicated-ip-caddy-on-demand-later
created: '2026-11-10T00:00:00'
updated: '2026-11-10T00:00:00'
rules:
- id: tetra-engine-is-the-backend
  description: New workloads (apps, sites, databases) are built on the Tetra Engine. Coolify is a
    transitional driver behind the WorkloadDriver seam; do not add new Coolify-only features, and
    never treat Coolify teams as a tenant boundary.
  severity: warn
- id: tetra-third-party-out-of-process
  description: Third-party (vendor) extensions never run in the control-plane process; they integrate
    as out-of-process apps through a manifest, a scoped token, webhooks and UI mount points or MCP.
  severity: warn
---

# ADR 0017: Tetra Engine is the deploy backend; Coolify is migrated off (roadmap 2026-11)

## Context
The project's documents disagreed. ADR 0004 (2026-07-01) chose "stay on Coolify, keep the Tetra Engine
as the escape hatch", while the charter (L28) and `docs/architecture/tetra-engine.md` said the engine
supersedes Coolify. Meanwhile the engine shipped catalog installs, git deploys, rollback and previews,
and 2026 research found Coolify unsuitable as a long-term multi-tenant engine: 70 published advisories
including cross-team IDOR and cross-tenant cloning flaws, breaking API changes in minor releases, Swarm
removal in v5 and no cross-server scheduling. The owner set the direction on 2026-11-10: a platform for
end customers and hosting companies between Coolify and Plesk, with the operator's own Plesk sites and
Coolify apps migrated first.

## Decision
1. **Supersedes ADR 0004 decision 2 ("stay on Coolify") only.** The Tetra Engine is the deploy backend.
   Coolify stays as a transitional `CoolifyDriver` until its apps are imported, then is removed. ADR
   0004's other rules stand: `tetra-tenancy-trusted-only`, `tetra-coolify-version-pin` (while Coolify
   runs), `tetra-no-terraform-bsl`, `tetra-mail-off-shared-host`.
2. **Adopts `docs/architecture/roadmap.md`** (phases 0–10) as the plan of record, replacing ADR 0004's
   P0–P6 list.
3. **Tenancy target:** platform → reseller → customer → team member, modelled with `tenants.parent_id`,
   a closure table and memberships; vendors are marketplace authors, not a tenant level.
4. **Plugin kernel v2** extends ADR 0007: plugins carry a manifest with entitlement and licence fields
   and are toggled at request time; third-party code stays out-of-process.

## Consequences
- New work targets the engine; Coolify code gets bug and security fixes only.
- Leaving Plesk requires a second server with its own IPv4 (ADR 0009 stage 2), because Plesk keeps :443
  on the current address.
- Follow-up ADRs are expected for Postgres as system of record, the org/authorisation model, the
  WorkloadDriver/apps resource, nodes and the agent, the task runner, the site type, importers,
  entitlements and billing.
- The tetrahedron mark in ADR 0003 still names Coolify as a vertex; that branding text should be revised
  separately.
