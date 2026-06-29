# Tenants & Plans Foundation — Design Spec

> Status: **draft for review** (2026-06-29, v2 — hardened after a 4-lens adversarial review).
> First slice of the multi-customer SaaS layer. Follow-ups (own specs): Billing (Stripe), Hard isolation
> (gVisor + real cgroup limits), Usage metering, Custom domains, Teams/members.
>
> **v2 changes from review (critical):** signup now requires fixing the existing **fail-open isolation** +
> retrofitting **platform-admin gates on pre-existing endpoints** + **central tenant-status enforcement**
> (all in scope); real container CPU/mem limits **descoped to bookkeeping** (→ isolation slice); quota
> reservation made **atomic before the async build**; migration rewritten to use explicit `ALTER`s;
> `is_active` resolved to a **derived read-only property** over `status`.

## Context

Tetra Host is an independent Docker-native PaaS aiming to be a **multi-customer SaaS**. It has a `Tenant`
model, `AdminUser` (`tenant_id`), `TenantResource` (+`TenantResourceFilter`) for scoping, and Apps / git
deploy / Caddy edge all run tenant-scoped. But there is **no self-serve signup, no roles, no plans, no
quotas**, and — critically — the isolation primitive **fails open** and several privileged endpoints are
**unguarded**. Those gaps are harmless today (effectively one real tenant) but become **cross-tenant
breaches the instant signup ships**, so this slice must close them.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Onboarding | **Self-serve signup, admin approves** — new tenants start `pending`, inactive until a platform admin activates them. |
| Quota dimensions | Plan **defines all four** (apps, custom-domains, CPU/mem pool, disk). **Functional this slice: app-count (enforced) + CPU/mem (allocation bookkeeping).** Domains + disk are **advisory** (defined, displayed labeled "not yet enforced"). |
| Plan catalog | **DB-managed with a full admin UI** (create/edit/archive). |
| Teams/roles | **Single owner per tenant + a `platform_admin` role** for staff. Teammate invites deferred. |

## Security prerequisites — IN SCOPE, must land with this slice

These three are not optional follow-ups; signup is unsafe without them.

1. **Isolation fails CLOSED for customer tenants.** Today `TenantResourceFilter.is_resource_accessible` and
   every `filter_*` return **full unfiltered** provider data when a tenant has no mappings (`not mapped_ids`),
   and `_strict_mode()` keys on `tenant_count <= 1`. A fresh signup tenant has zero mappings → it would see
   and mutate **all** Coolify apps / Cloudflare zones / Mailcow domains. Fix: add **`Tenant.is_platform_scope`**
   (bool, seeded `true` ONLY for the legacy/bootstrap tenant). `is_resource_accessible` and all `filter_*`
   fall open **only** when `tenant.is_platform_scope` is true; every other tenant is **deny-by-default**
   (empty mapped set → access to nothing). Remove the `tenant_count`-based `_strict_mode`. Tests: a second
   tenant with zero mappings sees `[]` for sites/dns/mail and gets 403 on `is_resource_accessible`.

2. **Retrofit `require_platform_admin` onto existing privileged endpoints.** These currently gate on "any
   authenticated admin" and would let an owner self-approve / take over another tenant:
   `POST /api/v1/tenants`, `GET /api/v1/tenants`, `/tenants/{slug}/activate|deactivate`,
   `POST /api/v1/tenant-admins`, `POST /api/v1/tenant-resources`, **and every mutating route + the index in
   `app/modules/admin/routes.py`**. All become platform-admin-only. Tests: owner token → 403 on each.

3. **Enforce tenant status centrally, not per-route.** Add the check **inside** `get_current_api_admin`
   (`app/api/routes.py`) and `get_current_admin` (`app/routes/deps.py`): the admin's `tenant` is already
   eager-loaded; for any **non-`platform_admin`** on an **unsafe method** (POST/PUT/PATCH/DELETE), require
   `tenant.status == "active"` (read live from the loaded row, never from the token snapshot) else 403. This
   makes pending/suspended enforcement un-forgettable and gives **immediate revocation** on suspend (the
   stateless token isn't trusted for status). `require_active_tenant` remains as defense-in-depth on the two
   primary mutating routes. Tests: suspended-tenant token → 403 on a deploy route with no explicit decorator.

## Approach

- **Reuse `AdminUser` + add `role`** (`platform_admin` | `owner`); no parallel Customer table.
- **Central `QuotaService`** consulted by each mutating action, with **atomic reservation**.
- **Allocation-based quotas**, but **real cgroup limits are descoped** to the isolation slice — this slice
  enforces **app-count** and records **CPU/mem allocation** (bookkeeping for the pool); disk + domains are
  advisory.
- **Plugin-modular** (charter): new `plans` module; `quota` shared service; signup extends `auth`+public.

## Data model

**New `Plan`** (`app/models/plan.py`, `plans` module): `key` (unique), `name`, `description`, `price_cents`,
`currency` ("usd"), `stripe_price_id` (reserved), quota cols `max_apps`, `max_domains`, `cpu_millicores`,
`mem_mb`, `disk_mb`, `is_archived`, `sort_order`, timestamps.

**`Tenant` gains** `plan_id` (FK→Plan, nullable → resolved via a single `effective_plan()` resolver that
falls back to `default_plan_key`), `status` (`pending`|`active`|`suspended`|`rejected`), and
`is_platform_scope` (bool, default false). **`is_active` becomes a read-only derived property**
(`status == "active"`) — **no stored column write**; the existing `is_active` column is dropped/migrated and
the ~15 readers keep working through the property. Activate/deactivate routes are rewritten to set `status`.

**`AdminUser` gains** `role` (`platform_admin`|`owner`, default `owner`). `role` and `plan_id` are **never**
accepted from owner-reachable request bodies (explicit allow-lists; ignore client-supplied `role`).

**App allocation:** `TenantResource` (app rows) gains `cpu_millicores`/`mem_mb`/`disk_mb`, **backfilled to the
config defaults** (not NULL — `SUM` ignores NULL and would undercount). `usage()` sums these; a `pending`
reservation row counts too (see Quota).

**Enum vocab as constants** (single source of truth) for `status` and `role` — service layer validates on
write (no free-text drift).

**Default plans** seeded idempotently (editable): numbers must satisfy
`max_apps * default_app_cpu_millicores <= cpu_millicores` etc. (e.g. Free 1/0/500m/512MB/2GB;
Pro 10/5/**8000m**/8GB/40GB; Business 50/25/40000m/64GB/400GB — Pro CPU raised so 10 apps × 500m fits).

**Config:** `default_app_cpu_millicores` (500), `default_app_mem_mb` (512), `default_app_disk_mb` (2048),
`default_plan_key` ("free"), `signup_rate_per_hour`, `max_pending_tenants`.

## Migration & backfill (`_upgrade_existing_schema`, Postgres + SQLite)

`create_all` **only** creates the new `plans` table — it never adds columns to existing tables. Every new
column is an **explicit, individually-guarded** `ALTER TABLE ADD COLUMN` (inspect-then-add, the existing
pattern), re-entrant after partial failure (SQLite DDL auto-commits), Postgres-compatible. Ordered:
1. Seed default plans (idempotent on `key`) — **before** any `plan_id` update.
2. `ALTER` add `tenants.status DEFAULT 'active'`; then `UPDATE tenants SET status='suspended' WHERE is_active=0`
   (derive from the old flag so deactivated tenants stay locked); add `tenants.is_platform_scope DEFAULT false`,
   then set `true` for the bootstrap/default tenant only; add `tenants.plan_id`, then
   `UPDATE … plan_id=(default Free) WHERE plan_id IS NULL`. Then drop/retire the `is_active` column (or stop
   writing it; the property derives from `status`).
3. `ALTER` add `admin_users.role DEFAULT 'owner'`; `UPDATE … role='platform_admin'` matching the
   **normalized** `ADMIN_BOOTSTRAP_EMAIL`; **fallback: if no match, promote the oldest admin**, and **assert
   ≥1 platform_admin exists** (log loudly otherwise) so staff endpoints are never locked out. The bootstrap
   tenant's admins are `platform_admin` (internal), not `owner`.
4. `ALTER` add `tenant_resources.cpu_millicores/mem_mb/disk_mb`; `UPDATE` existing app rows to the config
   defaults.

Test: run `init_db` twice (idempotent); start from a prior-schema snapshot and assert every column present;
`is_active=0` tenant → `status='suspended'`; ≥1 platform_admin.

## Onboarding & approval flow

1. **Register** — Next.js console page → public `POST /api/v1/auth/signup` (no auth, **rate-limited per-IP +
   a global `max_pending_tenants` cap**, reusing `app.state.rate_limiter`; password policy **≥10 chars**).
   Creates `Tenant(status="pending", is_platform_scope=false, plan=default Free)` + `AdminUser(role="owner")`,
   password via `AuthService.hash_password`. Email normalized. **Surface: Next.js console only** for v1.
2. **Auto-login is restricted**: signup issues a session, but because status is enforced centrally, a pending
   owner can only reach the **read-only** console + the "awaiting approval" screen — **zero** mutating routes.
3. **Approval queue (platform admin)**: lists `pending` tenants → **Approve** (`status="active"`, confirm/assign
   plan) or **Reject** (`status="rejected"`). Writes an **AuditEvent**.
4. **Reads stay available** while pending/suspended/rejected; only writes are blocked. Running apps are
   **never auto-killed** on suspend; in-flight deploys are allowed to finish.

Email enumeration: signup returns a **non-distinguishing** response for the duplicate-email case (handle the
duplicate server-side; don't expose a 409 that confirms an email exists) — or, if 409 is kept, it's hard
rate-limited and the trade-off documented.

## Authorization, roles & lifecycle

- `role` surfaced in the auth contract. **`require_platform_admin`** gates all staff endpoints (new + the
  retrofit list above). Owners scoped to their tenant via the now-**fail-closed** `TenantResourceFilter`.
- **Central status gate** (prerequisite #3) is the source of truth; `require_active_tenant` is defense-in-depth.
- **State machine:** `pending → active` (approve) | `pending → rejected` (reject) | `active → suspended`
  (suspend) | `suspended → active` (reactivate). Each transition is platform-admin-only + audited. Tenant
  **deletion is explicitly OUT of scope** (suspended/rejected tenants persist).
- **Single-owner invariant**: signup creates exactly one `owner`; the legacy multi-admin `/tenant-admins`
  path is platform-admin-only. (Formal `unique(tenant_id) where role='owner'` deferred with teams.)

## Quota enforcement (`app/services/quota.py`)

`QuotaService(session, tenant_id)`:
- **`usage()`** → `{apps, cpu_millicores, mem_mb, disk_mb, domains}`: counts the tenant's app `TenantResource`
  rows **plus in-flight `Deployment` rows in non-terminal states**, and sums allocation columns (COALESCE to
  defaults). This closes the async-deploy gap where in-flight builds were invisible.
- **`check_and_reserve(allocation)`** → in **one transaction**, take a **per-tenant lock** (Postgres
  `pg_advisory_xact_lock`/`SELECT … FOR UPDATE`; SQLite write lock), re-read usage, and if `apps+1 > max_apps`
  raise `QuotaExceeded(code, reason, limit, used)`; **else insert the app `TenantResource` reservation row
  (with allocation) in the same committed transaction, before any build.** Real method names:
  `AppsService.install_for_tenant` (request session) and `DeploysService.start_deploy_for_tenant` (its own
  `session_scope`, before `asyncio.create_task`).
- **Reservation lifecycle**: a **failed** build/engine step must **release** the reservation (delete the row)
  — the `_run_deploy` except handlers + install error path do this — so failed deploys don't permanently
  consume quota. (`never-auto-delete` applies to *running* apps, not failed reservations.)
- **Enforced this slice: app-count only.** CPU/mem are **recorded** (allocation) for the future pool +
  isolation slice but **not rejected on**. **Disk + domains are advisory** — never raise; `check_domain()` is
  **dropped** from this slice (lands with the custom-domains spec that has a Domain model).

**Errors:** a dedicated **FastAPI exception handler** maps `QuotaExceeded` → **HTTP 402** with body
`{error:"quota_exceeded", reason, limit, used}` (the existing `_engine_exc_to_http` stringifies and loses
fields, so a handler is required). The deploy check runs **synchronously in `start_deploy_for_tenant`** so the
402 returns on the POST, not buried in a background log. **Gate order: status (403) before quota (402).**
Clients branch on the machine-readable `error` code, not the HTTP number (so billing can later add a distinct
payment-402).

## Audit

Write `AuditEvent` (existing model) for: tenant approve / reject / suspend / reactivate, plan
create/edit/archive, plan assignment, role change. Signup must not log request bodies (passwords); passwords
hashed only; 402 bodies expose only the caller's own usage/limit.

## Console surfaces (+ CLI parity)

- Public **Register** page; **pending/suspended/rejected** gate screen (reads only).
- **Plans admin** (platform_admin): table + create/edit/archive form; **plan-save validates**
  `max_apps*default_alloc <= pool` and surfaces "effective max apps at default allocation".
- **Tenants admin** (platform_admin): all tenants w/ status + plan; approve/reject/suspend/**reactivate**;
  assign plan.
- **Plan & Usage** (owner): current plan + usage meters; **disk + domains meters visibly labeled "not yet
  enforced."**
- Role-conditional nav. **CLI parity**: `tetra plans …`, `tetra tenants list|approve|reject|suspend|reactivate`,
  `tetra usage`.

## Testing

- **Security prerequisites**: second tenant w/ zero mappings sees `[]` + 403 (fail-closed); owner token → 403
  on each retrofitted endpoint; suspended-token → 403 on an undecorated deploy route (central gate).
- **Quota**: 5 concurrent installs **and** 5 concurrent `POST /deploys/git` on a `max_apps=1` plan → exactly
  1 app row, 4×402; failed build releases the reservation; over-disk-but-under-count deploy is **allowed**
  (disk advisory).
- **Migration**: idempotent twice; prior-schema snapshot → all columns; `is_active=0`→`suspended`; ≥1
  platform_admin (incl. rotated-bootstrap-email fallback).
- **Auth/roles**: signup→pending→403 on writes; approve→unlocks; owner setting `role`/`plan_id` via any body
  → ignored/403; plan CRUD owner-forbidden.
- **Frontend/CLI** smoke tests for register, plans admin (incl. save-validation), usage meters, pending gate;
  CLI request shapes.

## Build order (land in safe increments; all one spec)

1. Plan model + admin CRUD + `role` + `require_platform_admin` retrofit + migration.
2. Fail-closed isolation + central status gate + signup + approval lifecycle.
3. Allocation columns + `QuotaService.usage` + **atomic app-count reservation** + 402 handler.
4. (Slippable to isolation slice) CPU/mem **enforcement** + real container limits.

## Out of scope → future specs

Stripe billing/checkout/invoices; live usage metering; **real cgroup CPU/mem/disk limits + gVisor**; the
custom-domains feature + `check_domain`; teammate invites / member roles / RBAC; email verification; tenant
deletion; plan-change proration; moving the in-memory rate limiter to a shared store (note it's best-effort
under multi-worker — pin single-worker or accept best-effort for now).

## Risks / open items

- `TenantResource` overloaded with allocation columns (vs a dedicated `App` model) — accepted; revisit later.
- In-memory rate limiter is per-process — fine at current single-worker scale; flagged for the billing era.
- Descoping CPU/mem **enforcement** means the pool is bookkeeping-only this slice; the owner UI must not imply
  CPU/mem are hard-enforced yet (label like disk/domains until step 4 / isolation slice lands).
