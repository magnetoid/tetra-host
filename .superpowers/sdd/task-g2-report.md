# Task G2 Report — Post-Deploy Backend Cleanup

## D1 — git-deploy over-quota → 402 test

**What changed:** Added `test_git_deploy_over_quota_returns_402` to `tests/test_quota.py`.

**How it works:** Seeds a plan with `max_apps=1`, a tenant with one already-reserved `TenantResource(resource_type=app)`, then POSTs `POST /api/v1/deploys/git`. The builder and engine are monkeypatched to `AssertionError` so they never execute — the quota check inside `start_deploy_for_tenant` (`app/modules/deploys/service.py:87`) fires first via `QuotaService.check_and_reserve`, raising `QuotaExceeded`, which the registered 402 handler in `app/main.py:76` converts to `{"error":"quota_exceeded","reason":"apps","limit":1,"used":1}`.

**Files:**
- `tests/test_quota.py` — added `_seed_git_deploy_quota_tenant`, `_login_git_deploy`, `test_git_deploy_over_quota_returns_402` (approx. lines 447–544)

**RED/GREEN:** Test passes GREEN. The code path was already correct; this test verifies it is not broken by future changes.

---

## D2 — Align `default_app_disk_mb` to 2048

**What changed:** `app/config.py` line 50:
```
# Before:
default_app_disk_mb: int = 1024
# After:
default_app_disk_mb: int = 2048
```

**Plan coherence:** The three seeded plans in `app/db/session.py` have `disk_mb` values of 2048, 40960, 409600. With `default_app_disk_mb=2048`, the per-app allocation now equals the Free plan limit (Free: 1 app × 2048 MB = 2048 MB ✓; Pro: 10 × 2048 = 20480 ≤ 40960 ✓; Business: 50 × 2048 = 102400 ≤ 409600 ✓).

**Migration backfill test:** `tests/test_migration_tenants_plans.py:122` asserts `app_row.disk_mb == settings.default_app_disk_mb` — it reads from settings directly, so it automatically tracks the new value. Confirmed: full suite passes with no changes to that test.

---

## D3 — Extract `list_databases_for_tenant` / `list_servers_for_tenant`

**New files:**
- `app/modules/databases/service.py` — `DatabasesService` with `list_databases()` and `list_databases_for_tenant(session, tenant_id)`
- `app/modules/servers/service.py` — `ServersService` with `list_servers()` and `list_servers_for_tenant(session, tenant_id)`

Each service method mirrors `SitesService.list_sites_for_tenant`: fetch from Coolify client, then apply `TenantResourceFilter.filter_databases` / `filter_servers`.

**Route changes:**

Before (`app/modules/databases/routes.py` `list_databases`):
```python
databases = await client.list_databases()
databases = await TenantResourceFilter(session, current_admin.tenant_id).filter_databases(databases)
```

After:
```python
service = DatabasesService(request)
databases = await service.list_databases_for_tenant(session, current_admin.tenant_id)
```

Same change applied to `app/modules/servers/routes.py` `list_servers`.

**Behavior:** Identical — `TenantResourceFilter.filter_databases` / `filter_servers` is still called, just through the service layer. No API surface change, no isolation regression.

---

## D4 — Pre-check duplicate app name on git-deploy

**What changed:** `app/modules/deploys/service.py` `start_deploy_for_tenant` (lines 83–97 after edit):

Added a pre-check inside the `session_scope` block, before `check_and_reserve`:
```python
existing = await session.scalar(
    select(TenantResource).where(
        TenantResource.tenant_id == (tenant_id or ""),
        TenantResource.provider == PROVIDER_DOCKER,
        TenantResource.resource_type == RESOURCE_TYPE_APP,
        TenantResource.external_id == project,
    )
)
if existing is not None:
    raise DockerEngineError(message=f"App '{project}' is already deployed.", code=409)
```

This mirrors the identical pattern in `app/modules/apps/service.py:134–143` (`install_for_tenant`). `DockerEngineError(code=409)` is converted to HTTP 409 by `_engine_exc_to_http` in `app/api/routes.py:952`.

Added imports: `TenantResource` from `app.models`, `PROVIDER_DOCKER`, `RESOURCE_TYPE_APP` from `app.models.tenant_resource`.

**New test:** `test_git_deploy_duplicate_name_returns_409` in `tests/test_apps_api.py` — seeds `app-writer` as an existing `TenantResource`, POSTs git-deploy with `name=app-writer`, asserts 409 and that only 1 `TenantResource` row exists afterward.

---

## Full suite result

```
176 passed, 7 skipped in 112s
```

(174 pre-existing + 2 new: `test_git_deploy_over_quota_returns_402`, `test_git_deploy_duplicate_name_returns_409`)

## ruff

```
All checks passed!
```

## D3 behavior preservation

The `TenantResourceFilter.filter_databases` / `filter_servers` logic is unchanged and still called on every list request. The only difference is the call site moves from inline in the route handler to inside a service method, consistent with the sites/dns/mail pattern. Existing isolation tests pass unchanged.
