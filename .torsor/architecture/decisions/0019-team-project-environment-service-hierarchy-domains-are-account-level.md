---
type: decision
status: accepted
tags:
- adr
links:
- 0018-tetra-host-replaces-coolify-and-plesk-coolify-and-plesk-are-import-sources-only
- 0007-platform-is-modular-and-plugin-based
created: '2026-11-14T00:00:00'
updated: '2026-11-14T00:00:00'
rules:
- id: tetra-services-live-in-environments
  description: Every workload (git app, template install, managed database, later image/worker) is a
    service inside a team → project → environment. New creation paths accept an environment_id and
    record the service there; stack names are globally unique on the host.
  severity: warn
---

# ADR 0019: Team → project → environment → service; domains are account-level

## Context
The console was a flat list of menus (Deploys, Apps, Databases, DNS, Mail…), so users could not tell
how things relate. The `projects` / `environments` / `apps` tables (migration 0005) existed only as an
index that `sync()` inferred after the fact (one project per stack); nothing was created *into* an
environment and managed databases were outside the hierarchy. Stack-name uniqueness was checked per
tenant in deploy/install, but compose project names and hostnames are global on the host.

On 2026-11-13/14 the owner set the structure, Coolify-like: the team is the root, then projects, and
everything else lives inside a project.

## Decision
1. **Hierarchy:** team (account: members, plan, billing, add-ons) → project → environment
   (production / staging / preview) → service.
2. **Service kinds:** `app` (git deploy, template install, import, preview) and `database` (managed
   database). Docker-image and worker/cron services come later as new kinds. `apps.kind` records it.
3. A service's **stack name is its runtime identity** and is globally unique on the host; deploy and
   install refuse a name another tenant already uses (409).
4. **Deployments belong to a service**: they are its version history, not a sibling menu.
5. Creation paths (git deploy, template install, database create) take an optional `environment_id`;
   when given, the service row is recorded there immediately. Without it `sync()` places it as before
   (databases fall back to a "databases" project).
6. **Domains are account-level** (a domain hub with DNS / Web / Mail tabs); hostnames point at services.
7. Env vars stay per service for now.

## Not decided here / later
Per-environment variables, environment-aware previews and domains, moving a service with runtime
effect, image/worker services, resellers (roadmap phase 5), and the AI agent surface — which will come
natively through Janus, not as separate AI features.

## Consequences
- The console gets project and environment screens with a "+ New service" picker (PR 2) and a domains
  hub (PR 3); old service URLs keep working.
- CLI (`--project/--env`) and MCP (`environment_id`) mirror placement at creation.
