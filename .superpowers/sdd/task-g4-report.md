# Task G4 — Coolify DB Provisioning + Backups

**Date:** 2026-06-30
**Branch:** feat/post-deploy-followups
**Commits:** 83feeb9 → 6f54ace (5 commits; squash commit follows)

---

## Verified Coolify v4 Endpoints

All endpoints confirmed from research doc (source: openapi.json at `https://raw.githubusercontent.com/coollabsio/coolify/main/openapi.json`):

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/databases/{db_type}` | Type-specific create per DB engine; required: `server_uuid`, `project_uuid`, `environment_name`, `name` |
| GET | `/api/v1/databases/{uuid}` | Already existed in `CoolifyClient.get_database` — not duplicated |
| GET | `/api/v1/databases/{uuid}/backups` | List scheduled backup configs |
| POST | `/api/v1/databases/{uuid}/backups` | Create backup config (frequency, retention_days, s3_storage_id) |

**No discrepancy** vs research sketch — endpoints match the documented v4 spec exactly.

Key structural fact confirmed: Coolify does NOT have a single `POST /api/v1/databases` endpoint. Each DB engine has its own path (`/databases/postgresql`, `/databases/mysql`, etc.). The `db_type` allow-list enforces this constraint and prevents arbitrary path construction from user input.

---

## CoolifyClient Methods Added (`app/services/coolify.py`)

**Module-level constant:**
```python
DB_TYPE_ALLOWLIST: frozenset[str] = frozenset({
    "postgresql", "mysql", "mariadb", "mongodb",
    "redis", "keydb", "dragonfly", "clickhouse",
})
```

**New methods:**

- `async def provision_database(self, db_type, server_uuid, project_uuid, environment_name, name, **opts) -> dict[str, Any]`
  - `POST /api/v1/databases/{db_type}` (type-specific path; db_type pre-validated by service)
  - Invalidates `coolify:databases` cache on success

- `async def list_database_backups(self, database_uuid) -> list[dict[str, Any]]`
  - `GET /api/v1/databases/{uuid}/backups`
  - Returns list or unwraps `data` key from dict response

- `async def create_database_backup(self, database_uuid, **config) -> dict[str, Any]`
  - `POST /api/v1/databases/{uuid}/backups`
  - Config kwargs: `frequency` (cron), `retention_days`, `s3_storage_id`

**Note:** `get_database` already existed at line ~802; not duplicated.

---

## DatabasesService Provision + Backup Flow (`app/modules/databases/service.py`)

### `provision_for_tenant`
1. `_require_actions()` → raises `ProviderAPIError(status_code=403)` if `ENABLE_PROVIDER_ACTIONS=false`
2. Validates `db_type` against `DB_TYPE_ALLOWLIST` → raises `ValueError` if invalid (route maps to HTTP 422)
3. Calls `client.provision_database(db_type, server_uuid, project_uuid, environment_name, name)`
4. Extracts `uuid` from Coolify response (`result.get("uuid") or result.get("id")`)
5. On success: creates `TenantResource(provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_DATABASE, external_id=uuid, display_name=name)`
6. On Coolify failure: `ProviderAPIError` propagates; no `TenantResource` created (clean failure)

### `_ensure_database_access`
- Calls `TenantResourceFilter(session, tenant_id).is_resource_accessible(provider=coolify, resource_type=database, external_id=db_uuid)`
- Platform-scope tenants fall-open (see `TenantResourceFilter._fall_open`)
- Regular tenants: must have a matching `TenantResource` row → raises `ProviderAPIError(403)` if absent

### `backups_for_tenant`
- `_ensure_database_access(session, tenant_id, db_uuid)` → then `client.list_database_backups(db_uuid)`

### `create_backup_for_tenant`
- `_require_actions()` → `_ensure_database_access(...)` → `client.create_database_backup(db_uuid, **config)`

---

## `/api/v1` Endpoints Added (`app/api/routes.py`)

| Method | Path | Request Contract | Response Contract | Gate |
|---|---|---|---|---|
| GET | `/api/v1/databases` | — | `list[DatabaseSummary]` | auth only |
| POST | `/api/v1/databases` | `DatabaseProvisionRequest` | `SiteActionResponse` | auth + ENABLE_PROVIDER_ACTIONS |
| GET | `/api/v1/databases/{db_uuid}/backups` | — | `list[BackupConfigSummary]` | auth + tenant ownership |
| POST | `/api/v1/databases/{db_uuid}/backups` | `BackupCreateRequest` | `SiteActionResponse` | auth + ENABLE_PROVIDER_ACTIONS + tenant ownership |

**Contracts added (`app/api/contracts.py`):**
- `DatabaseSummary` — `id, name, type, status, internal_db_url, image`
- `DatabaseProvisionRequest` — `db_type, name, server_uuid, project_uuid, environment_name` (no privilege fields)
- `BackupConfigSummary` — `id, frequency, retention_days, s3_storage_id`
- `BackupCreateRequest` — `frequency="0 2 * * *", retention_days=7, s3_storage_id=""`

---

## db_type Allow-List

`DB_TYPE_ALLOWLIST` (8 types): `clickhouse`, `dragonfly`, `keydb`, `mariadb`, `mongodb`, `mysql`, `postgresql`, `redis`

User-supplied `db_type` is validated in `DatabasesService.provision_for_tenant` **before** the value is interpolated into the Coolify API URL path. Unknown types raise `ValueError` → HTTP 422. This prevents:
- Arbitrary path construction (path traversal)
- Calls to Coolify endpoints outside the intended surface

---

## RED/GREEN Tests (`tests/test_databases_api.py`)

All 5 tests written RED (before implementation), then made GREEN:

| Test | What it covers |
|---|---|
| `test_provision_database_creates_tenant_resource` | POST /api/v1/databases → calls CoolifyClient.provision_database, creates TenantResource(database), new DB appears in GET /api/v1/databases list |
| `test_provision_database_blocked_when_actions_disabled` | 403 when ENABLE_PROVIDER_ACTIONS=false; CoolifyClient.provision_database is NOT called |
| `test_provision_database_invalid_db_type_returns_422` | 422 for db_type="oracle" (not in allow-list) |
| `test_backups_tenant_isolation` | GET /databases/{foreign_uuid}/backups → 403; tenant "dbt" cannot access "other" tenant's database |
| `test_create_backup_on_owned_database` | POST /databases/{owned_uuid}/backups → 200; CoolifyClient.create_database_backup called with correct uuid |

---

## Test Suite

| | Count |
|---|---|
| Before | 183 collected |
| After | 188 collected (+5) |
| Result | 181 passed, 7 skipped, 0 failures, 0 errors |

(The 7 skipped are the pre-existing quarantined `test_integrations` tests, unchanged.)

---

## ruff

`ruff check .` — **clean** (no errors after removing unused `import pytest` from test file)
