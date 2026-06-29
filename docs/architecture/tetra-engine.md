# Tetra Engine — Independent Docker-native Deployment & Hosting

> Status: **active design** (started 2026-06). Supersedes the prior "operate in symbiosis with
> Coolify / migrate everything to Coolify" charter rule. Coolify may remain for already-migrated
> legacy sites, but **new deployment + hosting is Tetra-owned and talks to Docker directly.**

## Decision

Tetra Host builds its **own** deployment engine ("Tetra Engine") that runs containers **directly on the
Docker Engine**, instead of orchestrating Coolify's API. The control plane (FastAPI `/api/v1` + Next.js
console + `tetra` CLI) is unchanged; underneath it, a Tetra-owned engine replaces the Coolify client as the
thing that builds images, runs containers, wires routing/TLS, and streams logs.

## Why this is the right call (from the June-2026 research sweep)

Every layer a PaaS needs is commodity open source we can compose directly — we don't need Coolify in the
data path:

- **Builders** — Railpack (Railway, **MIT**, BuildKit-native, 38% smaller Node / 77% smaller Python images
  than Nixpacks) and Nixpacks (**MIT**) are standalone source→OCI engines we shell out to. Dockerfile is the
  universal escape hatch. CNB/Paketo (Apache-2.0) is the better *standard* but heavier; revisit later.
- **Edge / TLS** — **Caddy on-demand TLS** issues a cert during the first TLS handshake for unknown SNIs
  (gated by an `ask` endpoint hitting our tenant DB) — the canonical "customer brings any domain, HTTPS just
  works" pattern Traefik can't do natively. Wildcard for our own `*.<tenant>.cloud-industry.com` via
  **Cloudflare DNS-01** (we already integrate Cloudflare).
- **Pre-defined containers** — the Coolify service-templates catalog is **Apache-2.0 base64 `docker-compose`
  files** (≈328 live / 600+ claimed, with category/tags/logo). They are just compose — **runnable directly
  via `docker compose`, no Coolify required.** We re-implement Coolify's `SERVICE_*` "magic variable"
  resolver (random passwords/users/base64, FQDN/URL) ourselves.
- **Vercel-quality features Coolify structurally can't give us** become possible once independent:
  live + failed build-log streaming, **true instant rollback** (immutable image tag + alias swap, not a
  rebuild), preview environments, per-tenant isolation & quotas.

Independence is what unlocks "Vercel quality." Coolify's rollback is web-UI-only/image-based/buggy
(`coolify#1976`), its build logs aren't streamable over the API, its teams are explicitly **not** a tenant
isolation boundary (`coolify#1820`), and it has had critical CVEs (Jan 2026). We stop inheriting those.

## Architecture (layers)

1. **Control plane** *(exists)* — FastAPI `/api/v1`, Next.js console, `tetra` CLI. Owns tenants, RBAC,
   quotas, audit (`AuditEvent`), and the premium UX. Dashboard↔CLI parity stays a rule.
2. **Tetra Engine** *(new — `app/services/docker_engine.py`)* — talks to the Docker Engine directly via the
   `docker` / `docker compose` CLIs over an **injectable async command runner** (testable in-process without
   a daemon, mirroring `tetra_cli`'s injectable httpx transport). Stack/container lifecycle, logs, stats.
3. **App catalog** *(new — `app/services/app_catalog.py`)* — fetches the compose template catalog
   (Coolify `service-templates.json`, cached), decodes base64 compose, and **renders** it independently:
   our own `SERVICE_PASSWORD_*` / `SERVICE_USER_*` / `SERVICE_BASE64_*` / `SERVICE_FQDN_*` / `SERVICE_URL_*`
   generator → concrete env map. One-click apps (WordPress first).
4. **Builder** *(later — `app/services/builder.py`)* — shell out to Railpack/Nixpacks: git repo → OCI image
   → local registry tag `app:sha-<commit>`. Dockerfile detected → build it directly (precedence rule).
   Mirror `@vercel/frameworks` (Apache-2.0) presets for zero-config framework detection + a Vercel-style
   "we detected Next.js" UX.
5. **Edge** *(later)* — **Caddy** for routing + automatic HTTPS (on-demand TLS via `ask` → tenant/domain
   table) and DNS-01 wildcards via Cloudflare.
6. **State** *(exists, extend)* — SQLAlchemy: deployments (immutable image tags), domains, `TenantResource`
   (add `provider="docker"`, `resource_type="app"`).

## Deployment model (Vercel-style, the load-bearing primitive)

The single idea that makes rollback instant, previews free, and promote atomic: **immutable, content-addressed
artifacts + a cheap pointer you repoint.**

- Every build → immutable image `registry/<app>:sha-<commit>`.
- "Deploy" = run that image as a service container.
- "Rollback / promote" = **repoint the running alias to a prior immutable tag — no rebuild.**
- Atomic flip: boot new container → poll health `/up` until green → switch the Caddy upstream → keep the
  previous container briefly for one-click revert (the Kamal/Dokku/CapRover pattern).

## Multi-tenant isolation (a Docker container is a resource boundary, not a security boundary)

Default for **semi-trusted** tenants (customers' own apps — the realistic case): **hardened containers** —
per-tenant **separate bridge network** (not one shared bridge with ICC off — that still leaks at L2),
mandatory `--memory` / `--cpus` / **`--pids-limit`** / device IO limits, dropped capabilities, read-only
rootfs where possible, **rootless / `userns-remap`**. Escalation for **untrusted** code: **gVisor (`runsc`)**
as opt-in runtime (best security-per-disk on a constrained box); microVM (Kata/Firecracker) or VM-per-tenant
only for genuinely hostile tenants. Tenant isolation is **ours to own** — never delegated to a shared engine.

## Disk discipline (the box is space-constrained)

Dedicate `/var/lib/docker` to its own partition; `daemon.json` log rotation (`local` driver, `max-size`) +
BuildKit GC cap (`builder.gc.defaultKeepStorage`); standardize tenants on a small set of **shared base
images** (content-addressed layers dedupe across all apps); scheduled **age-bounded** prunes
(`docker image prune -a --filter until=336h`, `docker builder prune --keep-storage`) — **never** a blind
`volume prune`, never mid-deploy.

## Build order (each slice independently shippable)

1. **Engine foundation + pre-defined container catalog → one-click WordPress via Docker.** ← in progress.
   `docker_engine.py` (lifecycle) + `app_catalog.py` (fetch/parse/render) + `apps` module
   (`/api/v1/apps` catalog/install/control, tenant-scoped) + console Apps page + `tetra apps …` CLI.
2. **Custom git deploy** via Railpack → image → run (zero-config framework presets, Dockerfile precedence).
3. **Caddy edge** + custom domains + automatic TLS (on-demand `ask`; Cloudflare DNS-01 wildcard).
4. **Immutable-image rollback / promote + preview environments** (the pointer model; PR bot comment).
5. **Per-tenant isolation hardening + quotas + observability** (metrics, streaming/failed build logs).

## Vercel-parity capability checklist (condensed, with effort on the new substrate)

| Capability | Effort | Note |
|---|---|---|
| Streaming build/run logs (live, colored, deep-linkable) | Easy–Med | We own the build process now → real streams, not polled snapshots |
| Legible deploy state model (queued/building/ready/error) | Easy | One enum rendered everywhere |
| Git push-to-deploy (GitHub App webhook) | Med | Our webhook receiver + builder |
| Custom domains + automatic TLS | Med | Caddy on-demand TLS + Cloudflare DNS |
| Per-environment + sensitive env vars, `env pull` | Easy–Med | Our model; redact secrets in logs |
| **Instant rollback / promote** (no rebuild) | Med | Immutable image tag + alias swap — now *possible* |
| Preview env per PR + PR bot comment + auto-cancel | Hard | Wildcard TLS + webhook orchestration |
| Deployment protection on previews | Med | Gate preview hosts at our edge/auth |

## Key sources (full set in the research notes)

Railpack <https://railpack.com/architecture/overview/> · Nixpacks <https://github.com/railwayapp/nixpacks> ·
`@vercel/frameworks` <https://github.com/vercel/vercel/tree/main/packages/frameworks> ·
Caddy on-demand TLS <https://caddyserver.com/docs/automatic-https> ·
Coolify service-templates (Apache-2.0 compose catalog) <https://github.com/coollabsio/coolify/blob/main/templates/service-templates.json> ·
Coolify isolation gap <https://github.com/coollabsio/coolify/discussions/1820> ·
Vercel instant rollback <https://vercel.com/docs/instant-rollback> ·
Docker resource limits <https://docs.docker.com/engine/containers/resource_constraints/> ·
gVisor <https://gvisor.dev/docs/architecture_guide/intro/> ·
Let's Encrypt rate limits <https://letsencrypt.org/docs/rate-limits/>
