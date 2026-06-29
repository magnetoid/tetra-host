# Tenants & Plans Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Tetra Host into a multi-customer SaaS foundation: self-serve signup + admin approval, DB-managed plans with a full admin UI, a `platform_admin`/`owner` role split, and allocation-based app-count quotas — while closing the existing fail-open isolation and unguarded-endpoint holes that make signup unsafe.

**Architecture:** FastAPI + async SQLAlchemy 2.0 with plugin modules under `app/modules/`. A new `Plan` model + `plans` plugin own the catalog; a shared `app/services/quota.py` enforces quotas atomically; signup extends `auth`; isolation/status/role become central (auth dependency + `TenantResourceFilter`). The Next.js console (`apps/web`) and `tetra_cli` get matching surfaces.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy (SQLite dev / Postgres prod), pydantic-settings, passlib (pbkdf2_sha256), Next.js 16 / React 19 / Tailwind v4, Font Awesome, argparse+httpx CLI, pytest TestClient + vitest.

## Global Constraints

- **Migrations:** schema changes go in `app/db/session.py::_upgrade_existing_schema` as **explicit, individually-guarded `ALTER TABLE ADD COLUMN`** (inspect-then-add). `create_all` only creates the brand-new `plans` table. Statements must be re-entrant (idempotent) and Postgres-compatible.
- **`is_active` is derived, not stored:** `Tenant.is_active` becomes a read-only property `status == "active"`. The stored `is_active` column is retired (stop writing it). Never write `is_active` directly.
- **Security invariants:** `role` and `plan_id` are NEVER accepted from owner-reachable request bodies. Isolation is **deny-by-default** for non-`is_platform_scope` tenants. Tenant status is enforced **centrally** in the auth dependency.
- **Charter rules:** every feature is a self-contained module + `plugin.py` registered in `app/modules/__init__.py`; keep `tetra_cli` at dashboard parity; route provider calls through `app/services/http.py`; all state-changing form POSTs validate CSRF (`verify_csrf_token`).
- **Status vocab:** `pending | active | suspended | rejected`. **Role vocab:** `platform_admin | owner`. Define once as module constants; validate on write.
- **Test pattern:** mirror `tests/test_apps_api.py` (seed tenant + `_login` → bearer; allowed vs 403). `tests/conftest.py` spins a throwaway SQLite DB per test.

---

## File Structure

**New backend**
- `app/models/plan.py` — `Plan` model + plan field constants.
- `app/modules/plans/__init__.py`, `service.py` (`PlanService`), `plugin.py` (`PlansPlugin`).
- `app/services/quota.py` — `QuotaService`, `QuotaExceeded`, `Allocation`.
- `tests/test_plans.py`, `tests/test_signup.py`, `tests/test_isolation_closed.py`, `tests/test_platform_admin_gates.py`, `tests/test_quota.py`, `tests/test_migration_tenants_plans.py`.

**Modified backend**
- `app/models/tenant.py` (status/plan_id/is_platform_scope + `is_active` property + STATUS_* consts), `app/models/admin.py` (role + ROLE_* consts), `app/models/tenant_resource.py` (allocation cols), `app/models/__init__.py` (export Plan).
- `app/config.py` (defaults), `app/db/session.py` (`_upgrade_existing_schema` + seed), `app/main.py` (register `PlansPlugin` + `QuotaExceeded` handler), `app/modules/__init__.py` (register plugin).
- `app/api/routes.py` (role in auth contract; `require_platform_admin`; retrofit gates; central status check in `get_current_api_admin`; plans CRUD; tenant approve/reject/suspend/reactivate; signup; usage), `app/routes/deps.py` (panel `get_current_admin` status gate + `require_platform_admin`), `app/api/contracts.py` (Plan/signup/usage/role/status), `app/services/tenant_resources.py` (fail-closed), `app/modules/auth/service.py` (`signup`, password policy, bootstrap role), `app/modules/apps/service.py` + `app/modules/deploys/service.py` (quota reserve/release).
- `tetra_cli/client.py` + `tetra_cli/cli.py` (plans/tenants/usage).

**Console (`apps/web/src`)**
- `app/auth/register/page.tsx` + `components/auth/register-form.tsx`; `app/(console)/plans/page.tsx` + `components/plans/*`; `app/(console)/tenants/page.tsx` + `components/tenants/*`; `app/(console)/usage/page.tsx` + `components/usage/usage-meters.tsx`; `components/shell/pending-gate.tsx`; `lib/navigation.ts` (role-conditional), `lib/types.ts`, `lib/icons.ts`.

---

## PHASE 1 — Plans, roles, platform-admin gating, migration

### Task 1.1: `Plan` model + constants

**Files:**
- Create: `app/models/plan.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_plans.py`

**Interfaces:**
- Produces: `Plan` (cols: `id, key, name, description, price_cents, currency, stripe_price_id, max_apps, max_domains, cpu_millicores, mem_mb, disk_mb, is_archived, sort_order, created_at, updated_at`).

- [ ] **Step 1: Write the failing test**
```python
# tests/test_plans.py
import asyncio
from app.db import session_scope
from app.models import Plan

def test_plan_round_trips():
    async def go():
        async with session_scope() as s:
            s.add(Plan(key="free", name="Free", max_apps=1, cpu_millicores=500, mem_mb=512, disk_mb=2048))
        async with session_scope() as s:
            from sqlalchemy import select
            p = (await s.scalars(select(Plan).where(Plan.key == "free"))).one()
            assert p.max_apps == 1 and p.currency == "usd" and p.is_archived is False
    asyncio.run(go())
```
- [ ] **Step 2: Run, verify it fails** — `pytest tests/test_plans.py::test_plan_round_trips -v` → FAIL (`ImportError: Plan`).
- [ ] **Step 3: Implement `app/models/plan.py`**
```python
from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def utc_now() -> datetime:
    return datetime.now(UTC)

class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    max_apps: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_domains: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cpu_millicores: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    mem_mb: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    disk_mb: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
```
Then add to `app/models/__init__.py`: `from app.models.plan import Plan` and add `"Plan"` to `__all__`.
- [ ] **Step 4: Run, verify pass** — `pytest tests/test_plans.py::test_plan_round_trips -v` → PASS.
- [ ] **Step 5: Commit** — `git add app/models/plan.py app/models/__init__.py tests/test_plans.py && git commit -m "feat(plans): Plan model"`

### Task 1.2: status/role constants + `Tenant`/`AdminUser` columns + `is_active` derived

**Files:** Modify `app/models/tenant.py`, `app/models/admin.py`; Test: extend `tests/test_plans.py`.

**Interfaces:**
- Produces: `app/models/tenant.py`: `TENANT_PENDING/ACTIVE/SUSPENDED/REJECTED` constants; `Tenant.status`, `Tenant.plan_id`, `Tenant.is_platform_scope`, `Tenant.is_active` (read-only `@property` → `status == TENANT_ACTIVE`). `app/models/admin.py`: `ROLE_PLATFORM_ADMIN`, `ROLE_OWNER`; `AdminUser.role`.

- [ ] **Step 1: Failing test**
```python
# tests/test_plans.py (append)
from app.models import Tenant
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING

def test_tenant_is_active_is_derived_from_status():
    t = Tenant(name="X", slug="x", status=TENANT_PENDING)
    assert t.is_active is False
    t.status = TENANT_ACTIVE
    assert t.is_active is True
```
- [ ] **Step 2: Run, fail** (`status`/`is_active` not as expected).
- [ ] **Step 3: Implement** — in `app/models/tenant.py`: add constants `TENANT_PENDING="pending"`, `TENANT_ACTIVE="active"`, `TENANT_SUSPENDED="suspended"`, `TENANT_REJECTED="rejected"`. Replace the `is_active` **column** with:
```python
    status: Mapped[str] = mapped_column(String(20), default=TENANT_ACTIVE, nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("plans.id"), nullable=True)
    is_platform_scope: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ...keep id/name/slug/timestamps...
    @property
    def is_active(self) -> bool:
        return self.status == TENANT_ACTIVE
```
In `app/models/admin.py`: add `ROLE_PLATFORM_ADMIN="platform_admin"`, `ROLE_OWNER="owner"`, and `role: Mapped[str] = mapped_column(String(20), default=ROLE_OWNER, nullable=False)`.
- [ ] **Step 4: Run, pass.** Also run `pytest -q` — expect failures in code that **constructs** `Tenant(is_active=...)` (api/routes.py, auth/service.py, admin/routes.py) and reads `Tenant.is_active` setter; those are fixed in Task 1.3.
- [ ] **Step 5: Commit** — `git commit -am "feat(tenants): status/role columns; is_active derived"`

### Task 1.3: Update `Tenant(...)` constructors + activate/deactivate writes to `status`

**Files:** Modify `app/modules/auth/service.py` (`ensure_default_tenant`, `ensure_bootstrap_admin`), `app/api/routes.py` (`api_create_tenant`, `api_activate_tenant`, `api_deactivate_tenant`), `app/modules/admin/routes.py` (tenant create/activate/deactivate), `app/db/session.py` (raw INSERT in `_upgrade_existing_schema` if it sets `is_active`).

- [ ] **Step 1: Grep** `git grep -n "is_active=True\|is_active=False\|\.is_active = " app/` — enumerate every write site.
- [ ] **Step 2: Replace** each `Tenant(... is_active=True)` → `Tenant(... status="active")`; each `tenant.is_active = True/False` → `tenant.status = "active"/"suspended"`. For the bootstrap/default tenant in `auth/service.py::ensure_default_tenant`, also set `is_platform_scope=True`. Leave `AdminUser.is_active` (separate column, unchanged).
- [ ] **Step 3: Run** `pytest -q` → green (existing tenant tests now pass against `status`).
- [ ] **Step 4: Commit** — `git commit -am "refactor(tenants): write status, not is_active; bootstrap tenant is_platform_scope"`

### Task 1.4: Migration — seed plans + ALTER existing tables

**Files:** Modify `app/db/session.py`; Test: `tests/test_migration_tenants_plans.py`.

**Interfaces:** Consumes Plan/Tenant/AdminUser. Produces a guarded `_upgrade_existing_schema` that adds `tenants.status/plan_id/is_platform_scope`, `admin_users.role`, seeds plans, and backfills.

- [ ] **Step 1: Read** `app/db/session.py:_upgrade_existing_schema` to copy the existing inspect-then-`ALTER` guard style (the `added_tenant_id`/`get_columns` pattern).
- [ ] **Step 2: Failing test**
```python
# tests/test_migration_tenants_plans.py
import asyncio
from sqlalchemy import select, text
from app.db import session_scope, init_db
from app.models import Plan, Tenant, AdminUser

def test_migration_is_idempotent_and_backfills():
    async def go():
        await init_db(); await init_db()  # twice = idempotent
        async with session_scope() as s:
            assert (await s.scalars(select(Plan).where(Plan.key == "free"))).first() is not None
            # at least one platform_admin exists
            admins = (await s.scalars(select(AdminUser))).all()
            assert any(a.role == "platform_admin" for a in admins) or len(admins) == 0
    asyncio.run(go())
```
- [ ] **Step 3: Run, fail** (no `free` plan / role missing).
- [ ] **Step 4: Implement** in `_upgrade_existing_schema` (after the existing block), using the existing `inspect`/`get_columns` helper to guard each ALTER. Pseudonature with real SQL (run via the same async connection the function already uses):
```python
# 1. add columns if missing (Postgres + SQLite compatible)
for table, col, ddl in [
    ("tenants", "status", "ALTER TABLE tenants ADD COLUMN status VARCHAR(20) DEFAULT 'active'"),
    ("tenants", "plan_id", "ALTER TABLE tenants ADD COLUMN plan_id VARCHAR(36)"),
    ("tenants", "is_platform_scope", "ALTER TABLE tenants ADD COLUMN is_platform_scope BOOLEAN DEFAULT 0"),
    ("admin_users", "role", "ALTER TABLE admin_users ADD COLUMN role VARCHAR(20) DEFAULT 'owner'"),
]:
    if col not in existing_columns(table):
        await conn.execute(text(ddl))
# 2. seed default plans idempotently (Free/Pro/Business) — INSERT ... WHERE NOT EXISTS on key
# 3. backfill (only if legacy is_active column still present):
if "is_active" in existing_columns("tenants"):
    await conn.execute(text("UPDATE tenants SET status='suspended' WHERE is_active = 0 AND status='active'"))
await conn.execute(text("UPDATE tenants SET is_platform_scope=1 WHERE slug='default'"))
await conn.execute(text(
    "UPDATE tenants SET plan_id=(SELECT id FROM plans WHERE key='free') WHERE plan_id IS NULL"))
# 4. role backfill: bootstrap email -> platform_admin, else fallback oldest
email = get_settings().admin_bootstrap_email.strip().lower()
await conn.execute(text("UPDATE admin_users SET role='platform_admin' WHERE lower(email)=:e"), {"e": email})
# ensure >=1 platform_admin: if none, promote oldest
count = (await conn.execute(text("SELECT COUNT(*) FROM admin_users WHERE role='platform_admin'"))).scalar()
if not count:
    await conn.execute(text(
        "UPDATE admin_users SET role='platform_admin' WHERE id=(SELECT id FROM admin_users ORDER BY created_at LIMIT 1)"))
```
(Provide a small `existing_columns(table)` helper mirroring the function's current `inspect` usage. Seed plans with the numbers from Global Constraints / spec: Free 1/0/500/512/2048; Pro 10/5/8000/8192/40960; Business 50/25/40000/65536/409600.)
- [ ] **Step 5: Run, pass** — `pytest tests/test_migration_tenants_plans.py -v`. Run full `pytest -q`.
- [ ] **Step 6: Commit** — `git commit -am "feat(db): migrate+seed plans, status/role/is_platform_scope backfill"`

### Task 1.5: `require_platform_admin` + retrofit existing privileged endpoints

**Files:** Modify `app/api/routes.py` (`get_current_api_admin` returns role; add `require_platform_admin`; gate `api_create_tenant`, `api_list_tenants`, `api_activate_tenant`, `api_deactivate_tenant`, `api_create_tenant_admin`, `api_create_tenant_resource`), `app/api/contracts.py` (`AdminSummary.role`), `app/routes/deps.py` (`require_platform_admin` for panel; gate `app/modules/admin/routes.py` mutating routes). Test: `tests/test_platform_admin_gates.py`.

**Interfaces:** Produces `require_platform_admin(current_admin = Depends(get_current_api_admin)) -> AdminUser` raising 403 unless `role == platform_admin`.

- [ ] **Step 1: Failing test**
```python
# tests/test_platform_admin_gates.py — seed an OWNER tenant+admin (role="owner"), login, assert 403
def test_owner_cannot_list_tenants(client, monkeypatch):
    asyncio.run(_seed_owner())          # tenant + AdminUser(role="owner")
    headers = _login(client, "owner@x.test", "pw")
    assert client.get("/api/v1/tenants", headers=headers).status_code == 403
    assert client.post("/api/v1/tenant-admins", headers=headers, json={...}).status_code == 403
```
- [ ] **Step 2: Run, fail** (returns 200).
- [ ] **Step 3: Implement** — add to `app/api/routes.py`:
```python
from app.models.admin import ROLE_PLATFORM_ADMIN
async def require_platform_admin(current_admin: AdminUser = Depends(get_current_api_admin)) -> AdminUser:
    if current_admin.role != ROLE_PLATFORM_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin only.")
    return current_admin
```
Add `_: AdminUser = Depends(require_platform_admin)` to each listed staff route (replace their `get_current_api_admin` dep where the route shouldn't be owner-reachable). Add `role: str` to `AdminSummary` + populate in `_admin_summary`. Mirror in `app/routes/deps.py` for the panel `require_admin` callers in `app/modules/admin/routes.py`.
- [ ] **Step 4: Run, pass.** Full `pytest -q`.
- [ ] **Step 5: Commit** — `git commit -am "feat(authz): require_platform_admin + retrofit existing privileged endpoints"`

### Task 1.6: Plan CRUD — `PlanService` + `plans` plugin + `/api/v1/plans`

**Files:** Create `app/modules/plans/{__init__,service,plugin}.py`; Modify `app/api/routes.py` (plans endpoints, platform-admin-gated for writes), `app/api/contracts.py` (`PlanSummary`, `PlanCreateRequest`, `PlanUpdateRequest`), `app/modules/__init__.py` (register). Test: extend `tests/test_plans.py`.

**Interfaces:** Produces `PlanService(session)` with `list_plans(include_archived=False)`, `create(**fields)`, `update(plan_id, **fields)`, `archive(plan_id)`, `get_default()`. Endpoints `GET /api/v1/plans` (any admin), `POST/PATCH/POST .../archive` (platform-admin). `PlanService.create/update` validates `max_apps*default_app_cpu_millicores <= cpu_millicores` and `…*mem <= mem_mb` → raise `ValueError` → 422.

- [ ] **Step 1: Failing tests** — owner GET /plans 200; owner POST /plans 403; platform_admin POST /plans 200 then GET shows it; POST with `max_apps=100, cpu_millicores=500` → 422 (validation).
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** `PlanService` (mirror `AuthService` style), the contracts, the endpoints (mirror existing `api_create_tenant` shape; writes use `Depends(require_platform_admin)`), and `PlansPlugin` (mirror `app/modules/dns/plugin.py`); register in `load_plugins()`. Plan-save validation helper raises `ValueError(msg)`; the route catches it → `HTTPException(422, msg)`.
- [ ] **Step 4: Run, pass.** Full suite.
- [ ] **Step 5: Commit** — `git commit -am "feat(plans): Plan CRUD service, plugin, /api/v1/plans (admin-gated + validated)"`

### Task 1.7: CLI `tetra plans` + console Plans admin page

**Files:** Modify `tetra_cli/client.py` (`plans()`, `plan_create()`, `plan_update()`, `plan_archive()`), `tetra_cli/cli.py` (`plans list|create|edit|archive`); Create `apps/web/src/app/(console)/plans/page.tsx` + `components/plans/plan-form.tsx`; Modify `apps/web/src/lib/{navigation,types}.ts`. Tests: `tests/test_cli.py` (request shapes), `apps/web/.../plan-form.test.tsx` (smoke).

- [ ] **Step 1: Failing CLI test** — mirror `test_client_zone_set_uses_patch`: `plans()` GETs `/api/v1/plans`; `plan_create` POSTs body.
- [ ] **Step 2–4:** implement client methods + argparse subcommands (mirror the `cf`/`apps` groups), the server page (platform-admin only; fetch `/plans`, render table + `PlanForm` that PATCHes `/api/proxy/plans/{id}`), nav entry conditional on `role === "platform_admin"`. Run `pytest tests/test_cli.py -q` and `pnpm --dir apps/web check`.
- [ ] **Step 5: Commit** — `git commit -am "feat(plans): tetra plans CLI + console Plans admin"`

---

## PHASE 2 — Fail-closed isolation, central status gate, signup + approval

### Task 2.1: Isolation fails closed (`is_platform_scope`)

**Files:** Modify `app/services/tenant_resources.py`; Test: `tests/test_isolation_closed.py`.

**Interfaces:** `TenantResourceFilter._strict_mode()` removed; fall-open only when the tenant row has `is_platform_scope`. Produces deny-by-default for all other tenants.

- [ ] **Step 1: Failing test** — seed a 2nd tenant (not platform-scope) with **zero** mappings; assert `is_resource_accessible(provider=cloudflare, type=dns_zone, external_id="anything")` is `False`, and `filter_dns([zone], [], selected_zone=zone.id)` returns `([], [], "")`.
```python
# tests/test_isolation_closed.py
def test_zero_mapping_tenant_is_denied(...):
    # seed Tenant(slug="cust", is_platform_scope=False) with no TenantResource rows
    flt = TenantResourceFilter(session, cust_tenant_id)
    assert asyncio.run(flt.is_resource_accessible(provider="cloudflare", resource_type="dns_zone", external_id="z1")) is False
```
- [ ] **Step 2: Run, fail** (currently returns True via fail-open).
- [ ] **Step 3: Implement** — add to `TenantResourceFilter.__init__` a load of the tenant's `is_platform_scope` (or pass it in). Replace every `if not mapped_ids and not await self._strict_mode():` early-return-full with `if not mapped_ids: return [] (or False) unless tenant.is_platform_scope`. Concretely: a helper `async def _fall_open(self) -> bool: return await self._is_platform_scope()`. `is_resource_accessible`: `return external_id in mapped_ids or (await self._fall_open())`. Each `filter_*`: `if await self._fall_open(): return <all>` else filter to mapped (empty mapped → empty).
- [ ] **Step 4: Run, pass.** Full `pytest -q` — confirm the bootstrap/default tenant (is_platform_scope=True, seeded in 1.3/1.4) still sees everything (existing tests rely on this).
- [ ] **Step 5: Commit** — `git commit -am "fix(isolation): deny-by-default; fall open only for is_platform_scope tenants"`

### Task 2.2: Central tenant-status gate in auth dependencies

**Files:** Modify `app/api/routes.py` (`get_current_api_admin`), `app/routes/deps.py` (`get_current_admin`). Test: `tests/test_signup.py` (suspended → 403 on a deploy route).

**Interfaces:** After loading `admin` (with eager `tenant`), for `admin.role != platform_admin` AND `request.method in {POST,PUT,PATCH,DELETE}`: require `admin.tenant and admin.tenant.status == "active"` else `HTTPException(403, "Tenant is not active.")`.

- [ ] **Step 1: Failing test** — seed an owner whose tenant `status="suspended"`, login (token still mints), `POST /api/v1/apps/whatever/start` → 403 (even though that route has no explicit status dep).
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** the method-aware check inside both dependencies (the `tenant` is already `selectinload`ed in `get_admin_by_id`). Read `request.method` (already a param/available). Platform admins bypass (they manage other tenants). Safe methods (GET/HEAD) bypass (reads allowed while pending/suspended).
- [ ] **Step 4: Run, pass.** Full suite — watch for tests that POST as a non-active seeded tenant; the `tests/test_apps_api.py` seed sets the writer tenant — ensure its `status` is `active` (it will be, default). 
- [ ] **Step 5: Commit** — `git commit -am "feat(authz): central tenant-status gate on unsafe methods"`

### Task 2.3: Signup endpoint (`/api/v1/auth/signup`) + password policy + rate limit

**Files:** Modify `app/modules/auth/service.py` (`signup(email, password, org_name) -> AdminUser`, `validate_password`), `app/api/routes.py` (`api_signup`, rate-limited), `app/api/contracts.py` (`SignupRequest`, reuse `AuthResponse`), `app/config.py` (`signup_rate_per_hour`, `max_pending_tenants`). Test: `tests/test_signup.py`.

**Interfaces:** `AuthService.signup` creates `Tenant(status="pending", is_platform_scope=False, plan_id=default Free)` + `AdminUser(role="owner")`; raises `ValueError` on weak password (<10 chars) and on duplicate email handled server-side (non-distinguishing response). `POST /api/v1/auth/signup` returns the same `AuthResponse` shape as login (auto-login token), but the token's tenant is pending → central gate blocks writes.

- [ ] **Step 1: Failing tests**
```python
def test_signup_creates_pending_owner_then_blocked(client):
    r = client.post("/api/v1/auth/signup", json={"email":"new@c.test","password":"longenough1","org_name":"Acme"})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "owner"
    # pending tenant: a write is blocked by the central gate
    assert client.post("/api/v1/apps/x/start", headers=headers).status_code == 403
def test_signup_weak_password_422(client):
    assert client.post("/api/v1/auth/signup", json={"email":"a@b.c","password":"short","org_name":"A"}).status_code == 422
```
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** `validate_password` (≥10 chars → else ValueError), `signup` (normalize email; if existing admin → return success-shaped response WITHOUT creating a duplicate, non-distinguishing; else create tenant+owner; resolve default plan via `PlanService.get_default`). Route: apply the login rate-limiter pattern from `app/modules/auth/routes.py` keyed on `request.client.host`; enforce `max_pending_tenants` (count pending tenants, 429 if over). On `ValueError` → 422.
- [ ] **Step 4: Run, pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(auth): self-serve signup (pending owner) + password policy + rate limit"`

### Task 2.4: Tenant approval lifecycle endpoints + audit

**Files:** Modify `app/api/routes.py` (`api_approve_tenant`, `api_reject_tenant`, `api_suspend_tenant`, `api_reactivate_tenant`, all `require_platform_admin`; write `AuditEvent`), `app/api/contracts.py` (`TenantSummary.status/plan`), `app/modules/auth/service.py` (helpers if needed). Test: `tests/test_signup.py` (approve unlocks).

**Interfaces:** `POST /api/v1/tenants/{slug}/approve|reject|suspend|reactivate` set status transitions (`pending→active`, `pending→rejected`, `active→suspended`, `suspended→active`) and `AuditEvent(actor_email, action, target=slug)`.

- [ ] **Step 1: Failing test** — signup → pending; platform_admin `POST /tenants/{slug}/approve` → 200; owner re-login → a write now succeeds (or returns a non-403 provider error, asserting the gate passed). Owner calling approve → 403.
- [ ] **Step 2–4:** implement transitions with explicit allowed-from checks (e.g. approve only from `pending`), audit writes (mirror existing `AuditEvent` usage), `TenantSummary` gains `status` + `plan_key`. Run suite.
- [ ] **Step 5: Commit** — `git commit -am "feat(tenants): approve/reject/suspend/reactivate lifecycle + audit"`

### Task 2.5: Console — Register page, pending gate, Tenants admin, CLI tenants

**Files:** Create `apps/web/src/app/auth/register/page.tsx` + `components/auth/register-form.tsx`, `components/shell/pending-gate.tsx`, `app/(console)/tenants/page.tsx` + `components/tenants/tenant-row-actions.tsx`; Modify `lib/auth.ts` (expose `tenant.status`/`role` in the session), `components/shell/app-shell.tsx` (render `PendingGate` when `status!=="active"` and role==="owner"), `lib/navigation.ts` (Tenants nav for platform_admin). CLI: `tetra_cli/client.py` (`tenants()`, `tenant_action(slug, action)`), `cli.py` (`tenants list|approve|reject|suspend|reactivate`). Tests: vitest smoke + `tests/test_cli.py`.

- [ ] **Step 1: Failing CLI test** — `tenant_action("acme","approve")` POSTs `/api/v1/tenants/acme/approve`.
- [ ] **Step 2–4:** implement. `getConsoleSession` (from the earlier auth fix) must include `tenant.status` + `admin.role` (extend `/auth/me` contract + `lib/types.ts`). `PendingGate`: full-screen "awaiting approval" when owner + non-active. Register form posts to `/api/auth/register` proxy → `/api/v1/auth/signup`, then routes to dashboard (which shows the gate). Tenants page (platform-admin): table + approve/suspend buttons (FA icons). Run `pnpm --dir apps/web check` + `pytest tests/test_cli.py`.
- [ ] **Step 5: Commit** — `git commit -am "feat(console): register, pending gate, tenants admin + tetra tenants CLI"`

---

## PHASE 3 — Allocation columns, QuotaService, atomic reservation, 402

### Task 3.1: `TenantResource` allocation columns + migration backfill to defaults

**Files:** Modify `app/models/tenant_resource.py` (add `cpu_millicores`, `mem_mb`, `disk_mb` nullable ints), `app/db/session.py` (ALTER + backfill existing app rows to config defaults), `app/config.py` (the `default_app_*` already added in 1.4 if not, add here). Test: extend `tests/test_migration_tenants_plans.py`.

- [ ] **Step 1–4:** add columns; in `_upgrade_existing_schema` add guarded ALTERs + `UPDATE tenant_resources SET cpu_millicores=:c, mem_mb=:m, disk_mb=:d WHERE resource_type='app' AND cpu_millicores IS NULL` with config defaults. Test: a seeded legacy app row reports the default after `init_db`.
- [ ] **Step 5: Commit** — `git commit -am "feat(quota): TenantResource allocation columns + backfill"`

### Task 3.2: `QuotaService` — usage + atomic `check_and_reserve`

**Files:** Create `app/services/quota.py`; Test: `tests/test_quota.py`.

**Interfaces:** Produces `Allocation(cpu_millicores, mem_mb, disk_mb)`, `QuotaExceeded(error="quota_exceeded", reason, limit, used)`, `QuotaService(session, tenant_id)` with:
- `async def usage() -> dict` — `{apps, cpu_millicores, mem_mb, disk_mb}`: count app `TenantResource` rows **+ Deployment rows in {queued,building}**, sum allocations (COALESCE to config defaults).
- `async def check_and_reserve(project, allocation, display_name) -> None` — within the passed session+a per-tenant lock: re-read app count; if `apps+1 > plan.max_apps` → raise `QuotaExceeded(reason="apps", limit, used)`; else `session.add(TenantResource(... allocation, display_name))`. (App-count enforced; CPU/mem/disk recorded only — NOT raised on, per spec.)
- `async def release(project)` — delete the reservation row (failed build).

- [ ] **Step 1: Failing tests** — plan max_apps=1; reserve app#1 OK; `check_and_reserve` for app#2 raises `QuotaExceeded` with `reason=="apps"`; `usage()` counts an in-flight Deployment(status="building"); `release` removes the row.
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** — resolve the plan via `tenant.plan` or default; lock per spec: on Postgres `await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:t))"), {"t": tenant_id})` (guard by dialect name; on SQLite the connection write-lock suffices — skip the advisory call). COALESCE allocations in Python (`row.cpu_millicores or default`).
- [ ] **Step 4: Run, pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(quota): QuotaService usage + atomic check_and_reserve + release"`

### Task 3.3: Wire quota into install + git-deploy (reserve before run, release on failure)

**Files:** Modify `app/modules/apps/service.py` (`install_for_tenant`: call `check_and_reserve` in the request session **before** `engine.deploy_stack`; the reservation row REPLACES the current `session.add(TenantResource)`; on engine failure, `release`), `app/modules/deploys/service.py` (`start_deploy_for_tenant`: inside its `session_scope`, before `asyncio.create_task`, `check_and_reserve`; `_run_deploy` except handlers call `release(project)`). Test: `tests/test_quota.py` (concurrent), `tests/test_apps_api.py` (install over quota → 402).

**Interfaces:** Consumes `QuotaService`. The app reservation row now carries allocation; `_record_app` in deploys is replaced by the pre-build reservation (no double insert).

- [ ] **Step 1: Failing tests** — on a `max_apps=1` plan: 2nd `POST /api/v1/apps/install` → 402 `{error:"quota_exceeded"}`; a deploy whose build fails leaves `usage().apps` back at prior count (release).
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** — replace the manual `TenantResource` insert in `install_for_tenant` with `quota.check_and_reserve(project, allocation, display_name)` (default `allocation` from config); wrap `engine.deploy_stack` so a `DockerEngineError` triggers `quota.release(project)` then re-raise. In `deploys`, call `check_and_reserve` in the committed `session_scope` block, drop `_record_app`, and add `release` to both `except` arms of `_run_deploy`.
- [ ] **Step 4: Run, pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(quota): atomic reservation in install + git-deploy; release on failure"`

### Task 3.4: `QuotaExceeded` → 402 exception handler

**Files:** Modify `app/main.py` (`app.add_exception_handler(QuotaExceeded, ...)` returning `JSONResponse(status_code=402, content={"error":"quota_exceeded","reason":...,"limit":...,"used":...})`); remove `QuotaExceeded` from any route `except` tuples (let it bubble to the handler). Test: covered by 3.3 (asserts 402 + body).

- [ ] **Step 1–4:** add the handler in `create_app()`; verify the 402 body shape in the 3.3 tests (assert `r.json()["error"] == "quota_exceeded"`). Ensure gate order: the central status gate (403) runs in the dependency before the handler body, so a non-active tenant gets 403 not 402.
- [ ] **Step 5: Commit** — `git commit -am "feat(quota): 402 exception handler with machine-readable body"`

### Task 3.5: Usage endpoint + console meters + `tetra usage`

**Files:** Modify `app/api/routes.py` (`GET /api/v1/usage` → plan + `usage()` for the caller's tenant), `app/api/contracts.py` (`UsageResponse`), `tetra_cli/{client,cli}.py` (`usage()` / `tetra usage`); Create `apps/web/src/app/(console)/usage/page.tsx` + `components/usage/usage-meters.tsx` (apps meter enforced; **disk + domains meters labeled "not yet enforced"**). Tests: `tests/test_cli.py`, vitest smoke.

- [ ] **Step 1–4:** implement; meters show `apps used/max`; disk/domains rendered with a muted "advisory" badge. Run `pytest tests/test_cli.py` + `pnpm --dir apps/web check`.
- [ ] **Step 5: Commit** — `git commit -am "feat(quota): /usage endpoint, console meters (advisory labels), tetra usage"`

---

## PHASE 4 — (Slippable) CPU/mem enforcement + real container limits

> May defer to the isolation slice without blocking Phases 1–3. If done here:

### Task 4.1: Enforce CPU/mem pool in `check_and_reserve` + inject container limits

**Files:** Modify `app/services/quota.py` (also raise `QuotaExceeded(reason="cpu"/"mem")` when the pool would be exceeded), `app/services/edge.py` or a new helper used by both `app_catalog.normalize_compose_for_engine` and `deploys.compose_for_image` to inject `mem_limit`/`cpus` onto the public service. Test: `tests/test_quota.py` (over-cpu → 402), `tests/test_edge.py`-style (rendered compose carries `mem_limit`).

- [ ] Add pool checks (still **skip disk** — advisory); add a single `apply_resource_limits(compose_yaml, allocation)` helper invoked in both install + deploy paths; test the rendered compose. Commit.

---

## Self-Review (against the spec)

**Spec coverage:**
- Security prereqs: isolation fail-closed (2.1 ✓), platform-admin retrofit (1.5 ✓), central status gate (2.2 ✓).
- Data model: Plan (1.1), status/role/is_platform_scope + is_active-derived (1.2–1.3), allocation cols (3.1) ✓.
- Migration: explicit ALTERs + seed + backfill + ≥1 platform_admin (1.4) ✓.
- Onboarding/approval: signup + rate limit + password (2.3), lifecycle + audit (2.4), register/pending/tenants UI (2.5) ✓.
- Quota: usage incl. in-flight + atomic reserve + release (3.2–3.3), 402 handler (3.4), advisory disk/domains + usage UI (3.5) ✓.
- CLI parity: plans (1.7), tenants (2.5), usage (3.5) ✓.
- Out of scope honored: no Stripe, no metering, no real cgroup limits except slippable 4.1, no `check_domain`, no tenant delete.

**Placeholder scan:** code shown for novel tasks; routine CRUD/UI tasks cite the exact existing pattern to mirror (e.g. `api_create_tenant`, `app/modules/dns/plugin.py`, `tests/test_apps_api.py`) rather than vague "implement CRUD". No "TBD".

**Type consistency:** `QuotaExceeded(error, reason, limit, used)`, `check_and_reserve(project, allocation, display_name)`, `release(project)`, `require_platform_admin`, `Tenant.is_active` (property), `TENANT_*`/`ROLE_*` constants used consistently across tasks.

**Known nuance for the implementer:** `get_current_api_admin` must read `request.method` for the status gate — it already receives `request: Request`. The deploy path's `QuotaService` binds to the `session_scope` session inside `start_deploy_for_tenant` (not the request session). Seed `status="active"` in existing test fixtures so prior tests stay green.
