# Tetra Host roadmap (2026-11)

Status: accepted 2026-11-10. Supersedes the phase list in ADR 0004 (P0–P6) and the build order in
`tetra-engine.md` where they conflict. Decision records: ADR 0017; ADR 0018 (2026-11-11) amends it —
the panel no longer manages Coolify apps, Coolify and Plesk are import sources only.

## Goal

A hosting platform for apps, AI workloads, websites (including PHP/WordPress), email and DNS, serving
both end customers and hosting companies. It is an open-source replacement for Coolify (developer
PaaS) and Plesk (traditional hosting panel): one control plane, separate panels per role, features as plugins that can
be switched on and off at runtime.

## Owner decisions this plan rests on

- **Roles:** platform super admin → hosting company (reseller) → customer → team member.
  A "vendor" is a third-party author who builds and sells plugins/apps in a marketplace; it is not a
  tenant level.
- **First customer is the operator:** the ~30 Plesk sites and the Coolify apps move onto the Tetra
  Engine first. The reseller layer comes right after.
- **Billing:** built in (plans, usage metering, Stripe, invoices) plus provisioning modules for
  WHMCS/Blesta/Upmind.
- **Licence:** undecided. Plugins carry `license`/`entitlement` fields; nothing is enforced until the
  business model is chosen.

## Starting point (HEAD 0a6773c)

- The native engine already does one-click catalog installs, git deploys, registry-backed rollback and
  previews, but only on the local host, with builds as in-process asyncio tasks.
- Tenancy is flat (`Tenant` has no parent); one user belongs to exactly one tenant; roles are four
  strings and `admin`/`member` behave the same.
- The plugin boundary covers only the legacy Jinja routes. All of `/api/v1` lives in
  `app/api/routes.py` (4,494 lines, 167 endpoints). Console nav is hard-coded.
- No payment provider, invoices, white-label, or provider abstraction. Production runs on SQLite.

## Market inputs (researched 2026-11)

- Coolify is not a durable engine for a multi-tenant product: 70 published advisories including 2026
  cross-team/cross-tenant flaws, breaking API changes in minor releases, Swarm removed in v5, no
  cross-server scheduling.
- No open-source panel offers multi-tier tenancy plus white-label (Dokploy keeps RBAC, SSO,
  white-label and audit in its proprietary directory). Enhance is the reference reseller panel.
- cPanel, Plesk and WHMCS raise prices every year; hosts are actively looking for alternatives.
- Durable bets: Postgres, OCI + BuildKit (Dockerfile, Railpack), Caddy on-demand TLS, pull-style node
  agents, reconciliation loops, gVisor for untrusted code, PowerDNS for own DNS, restic for backups.

## Architecture decisions

1. **One control plane, three panels in one Next.js app**: route groups `(platform)`, `(reseller)`,
   `(console)`. The backend drives navigation through `GET /api/v1/meta/capabilities`.
2. **Plugin kernel v2**: `PluginMeta` (`app/plugins.py`) grows into a manifest — `key`, `version`,
   `kind` (core/feature/provider), `requires`, `entitlement`, `license`, `audience`, `permissions`,
   `nav`, `api_router`, `models`, `subscribers`. Each plugin owns its API router, models, CLI commands
   and MCP tools.
3. **Runtime toggles**: routers are always mounted; `require_plugin(key)` returns 404
   (`plugin_disabled`) when off. One resolver checks installation → plan → organisation override. Only
   the installation level ships now (`plugin_state` table plus a `PLUGINS_DISABLED` kill switch); plan
   and org levels arrive with billing, behind the same function.
4. **One `AuthContext`** (user, org, role, permissions, visible org ids, impersonator) and a
   `require("dns.write")` dependency replace per-endpoint role checks. It lands before the org
   hierarchy so handlers are touched once.
5. **Org hierarchy in the database, no OpenFGA**: `tenants.parent_id` + `kind`, a `tenant_closure`
   table, and `memberships` (one login, many orgs). Depth is at most four.
6. **One `apps` resource** over engine stacks (the `apps` table, step 3 of the console redesign).
   Coolify is not a driver: ADR 0018 (2026-11-11) removed the panel's Coolify integration, and
   Coolify/Plesk are import sources only. `driver` stays on the row for other runtimes later.
7. **Postgres as the system of record; schema changes only through Alembic** (one linear chain).
8. **A plain Postgres task table** (`platform_tasks`, `FOR UPDATE SKIP LOCKED`, separate
   `python -m app.worker`), not Temporal or DBOS.
9. **Nodes**: an SSH bridge first (`DockerEngine` already accepts `DOCKER_HOST` through its env), then
   a Go agent with an outbound connection and desired-state reconciliation before the first external
   reseller.
10. **Edge**: Caddy on-demand TLS on a dedicated IPv4 (ADR 0009 stage 2). Plesk owns :443 on the only
    address, so a second server with its own IPv4 is a prerequisite for leaving Plesk.
11. **Third-party code never runs in-process**: vendors ship out-of-process apps (manifest, scoped
    token, webhooks, iframe/MCP).

## Phases

| # | Phase | Ships | Exit criteria |
|---|---|---|---|
| 0 | Hygiene | Green CI (ruff), dead legacy files removed, OpenAPI contract snapshot test, ADR 0017, refreshed `CLAUDE.md`/`.torsor/` | `ruff` and `pytest` green on main |
| 1 | Kernel + authz seam | Manifest; `app/api/deps.py`; `routes.py` becomes an aggregator and modules move one per PR (`jobs` first, then the engine cluster: apps, deploys, previews, domains, edge, webhooks, infra); install-level toggle; `/meta/capabilities`; `AuthContext`; `AuditService` with `tenant_id`; CLI and MCP split per plugin | OpenAPI snapshot unchanged; disabling a plugin returns 404 and removes it from nav, CLI and MCP without a restart |
| 2 | Postgres + tasks | Production on Postgres; real Alembic baseline; `init_db()` for SQLite tests only; `app/worker.py` + `platform_tasks`; builds off the web process; CI on both databases | Suite green on both; a build survives a web restart; `alembic check` clean |
| 3 | Unified apps + node 1 | `apps` table (engine only, ADR 0018); engine replacements for what Coolify gave the panel — managed databases + backups, volumes, restart, cancel, exec, build settings; `nodes` table, second server with its own IPv4, Caddy on-demand TLS, per-app network + cap-drop, Railpack, health-gated cutover | Managed databases and volumes work on the engine; a custom domain gets a certificate on node 1 without Cloudflare for SaaS |
| 4 | Dogfood migration | `site` type (PHP/WordPress/static, PHP version, per-site DB, SFTP, cron, WP-CLI tools, staging/clone, restic backups); Plesk→engine and Coolify→engine importers as per-site state machines; then operator mail to a dedicated Mailcow | All Coolify apps and Plesk sites served by the engine after a 7-day soak; a restore drill passes; Plesk switched off |
| 5 | Organisations | Hierarchy, memberships, roles, impersonation, branding by panel hostname, three panels; remaining routers moved | Isolation matrix (platform / reseller A / reseller B / customer) passes; one login switches orgs; a reseller hostname shows its branding |
| 6 | Commercial | Plan and org entitlements; all plan caps enforced; plan changes; metering into the existing ledger; Stripe; invoices; provisioning API + WHMCS module | Stripe test signup provisions a plan; a downgrade disables a plugin at runtime; WHMCS creates, suspends and terminates |
| 7 | Agent + isolation | Go agent replaces the SSH bridge; placement; node roles; site moves; gVisor option | Control-plane outage leaves sites serving and certificates issuing; an app moves nodes with no customer DNS change |
| 8 | Reseller mail + DNS | PowerDNS with branded nameservers; `DnsDriver`/`MailDriver`; per-reseller relay; domain resale | A reseller's customer uses branded nameservers and webmail |
| 9 | AI products | Remote MCP (Streamable HTTP + OAuth), gVisor sandboxes, agent hosting, per-key budgets | A remote MCP client completes OAuth and sees entitlement-filtered tools |
| 10 | Marketplace | Out-of-process vendor apps, vendor portal, revenue share | A sample app installs per org and receives signed webhooks |

Phase 7 must land before the first external reseller: strangers' workloads must not run beside the
control-plane database.

## Reused, not rewritten

`DockerEngine._docker(env=…)` for remote Docker; `TenantResourceFilter` (its 19 call sites inherit the
ancestor-scope change); `QuotaService`; the billing models (`PricingRule`, `ResellerCharge`,
`TenantCredit`); `ScheduledJob` (extended with `kind='command'`); the Cloudflare DNS module for
cutovers; `GET /api/v1/edge/ask` for on-demand TLS.

## Deliberately deferred

| Item | Trigger |
|---|---|
| OpenFGA / SpiceDB | Per-resource sharing or custom roles |
| Temporal / DBOS | Multi-day workflows or durable AI agents (inside that plugin only) |
| k3s / Talos | Several nodes needing automatic rescheduling or replicas |
| Kata / Firecracker | Dedicated hardware and hostile tenants |
| Lago / OpenMeter | Usage pricing beyond a few meters |
| Shared certificate storage | The same hostname served from more than one node |
| Licence enforcement on plugins | The business-model decision |
| In-process third-party plugins, module federation, Wasm | Never planned; vendors stay out-of-process |

## Risks

- **Cross-tenant leak** during the filter change in phase 5 — mitigated by the isolation matrix.
- **The SSH bridge becoming permanent** — phase 7 gates external resellers.
- **Per-site surprises** in Plesk (old PHP, `.htaccess`, cron, mail loopback) — 7-day soak with the
  source kept and one-record DNS rollback.
- **SQLite → Postgres data copy** — column-length audit first; rollback is the old `DATABASE_URL`.
- **The WHMCS module is PHP, a fourth language** — needs a recorded exception to ADR 0005; it lives in
  its own repository.

## Verification

- Per phase: the exit criteria above.
- Always: `pytest`, `ruff check .`, `pnpm web:check`; the OpenAPI snapshot guards the `/api/v1`
  contract while routers move.
- From phase 2: the suite on SQLite and Postgres; `alembic upgrade head` + `alembic check` on an empty
  database.
- From phase 5: `tests/test_cross_tenant_isolation.py`, `test_isolation_closed.py` and
  `test_privilege_escalation.py` extended with the platform / reseller / customer matrix.
- Dashboard ↔ CLI ↔ MCP parity (ADR 0012) checked for every plugin that moves.
