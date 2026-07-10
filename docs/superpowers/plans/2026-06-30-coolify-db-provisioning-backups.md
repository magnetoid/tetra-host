# Coolify Database Provisioning + Backups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tenant-scoped Coolify database provisioning + backup management behind `/api/v1/databases` endpoints, with TDD-first tests that mirror the apps API test pattern.

**Architecture:** `CoolifyClient` gets four new methods (`provision_database`, `get_database`, `list_database_backups`, `create_database_backup`); `DatabasesService` gets three new methods (`provision_for_tenant`, `backups_for_tenant`, `create_backup_for_tenant`) with `_ensure_database_access` isolation guard and ENABLE_PROVIDER_ACTIONS gating; four new `/api/v1/databases` route handlers + three new Pydantic contracts are added to the existing `routes.py`/`contracts.py`.

**Tech Stack:** Python 3.12, FastAPI, async SQLAlchemy 2.0, Pydantic v2, pytest + httpx TestClient, ruff linter, Coolify v4 API.

## Global Constraints

- All provider calls via `app/services/http.py` → `request_json` → raises `ProviderAPIError`
- Tenant isolation via `TenantResource` + `_ensure_database_access` (mirror `SitesService._ensure_tenant_access`)
- All write endpoints gated by `ENABLE_PROVIDER_ACTIONS` (return 403 when disabled)
- `db_type` restricted to known allow-list — never build a URL path from raw user input
- No quota enforcement for databases yet (future; isolation via TenantResource still applies)
- No owner-writable privilege fields in any request body
- Full pytest suite must stay green (183 tests collected pre-task)
- `ruff check .` must stay clean after every task
- Branch: `feat/post-deploy-followups`
- Commit after each task

---

## Verified Coolify v4 API Endpoints (from research doc)

Provisioning (POST per type, not a single generic endpoint):
- `POST /api/v1/databases/postgresql` — required body: `server_uuid`, `project_uuid`, `environment_name`, `name`
- `POST /api/v1/databases/mysql` — same required fields
- `POST /api/v1/databases/mariadb` — same
- `POST /api/v1/databases/mongodb` — same
- `POST /api/v1/databases/redis` — same
- `POST /api/v1/databases/keydb` — same
- `POST /api/v1/databases/dragonfly` — same
- `POST /api/v1/databases/clickhouse` — same

Read/backup:
- `GET /api/v1/databases/{uuid}` — get database
- `GET /api/v1/databases/{uuid}/backups` — list backup configs
- `POST /api/v1/databases/{uuid}/backups` — create backup config (s3_*, frequency, retention)

**db_type allow-list:** `{"postgresql", "mysql", "mariadb", "mongodb", "redis", "keydb", "dragonfly", "clickhouse"}`

---

## File Map

| File | Change |
|---|---|
| `app/services/coolify.py` | Add 4 new methods to `CoolifyClient` |
| `app/modules/databases/service.py` | Add `provision_for_tenant`, `backups_for_tenant`, `create_backup_for_tenant`, `_ensure_database_access` |
| `app/api/contracts.py` | Add `DatabaseSummary`, `DatabaseProvisionRequest`, `BackupConfigSummary`, `BackupCreateRequest` |
| `app/api/routes.py` | Add 4 route handlers + import new contracts |
| `tests/test_databases_api.py` | New test file (5 test functions) |

---

## Task 1: CoolifyClient — `provision_database` + `get_database`

**Files:**
- Modify: `app/services/coolify.py` (after the existing `restart_database` method at ~line 844)

**Interfaces:**
- Produces:
  - `async def provision_database(self, db_type: str, server_uuid: str, project_uuid: str, environment_name: str, name: str, **opts: object) -> dict[str, Any]`
  - `async def get_database(self, database_uuid: str) -> CoolifyDatabase | None`
  - `DB_TYPE_ALLOWLIST: frozenset[str]` module-level constant

- [ ] **Step 1: Write the failing tests**

Create `tests/test_databases_api.py` with import stubs only (the route does not exist yet, so we can at minimum import the module and verify the new client methods don't exist):

```python
# tests/test_databases_api.py
"""Tests for /api/v1/databases — Coolify DB provisioning + backups (tenant-scoped).

Mirrors tests/test_apps_api.py pattern:
- asyncio.run(_seed_*) for DB fixtures
- monkeypatch on CoolifyClient methods
- enable_provider_actions toggled via monkeypatch
"""
import asyncio

import pytest

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_DATABASE
from app.modules.auth.service import AuthService
from app.services.coolify import CoolifyClient


async def _seed_db_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="DB Tenant", slug="dbt", status="active")
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@db.test",
                full_name="DB Owner",
                password_hash=auth_service.hash_password("db-password"),
                is_active=True,
            )
        )
        # Pre-assign an existing database to this tenant
        session.add(
            TenantResource(
                tenant_id=tenant.id,
                provider=PROVIDER_COOLIFY,
                resource_type=RESOURCE_TYPE_DATABASE,
                external_id="db-uuid-existing",
                display_name="Existing DB",
            )
        )


async def _seed_other_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Other Tenant", slug="other", status="active")
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@other.test",
                full_name="Other Owner",
                password_hash=auth_service.hash_password("other-password"),
                is_active=True,
            )
        )
        # Other tenant has a different database
        session.add(
            TenantResource(
                tenant_id=tenant.id,
                provider=PROVIDER_COOLIFY,
                resource_type=RESOURCE_TYPE_DATABASE,
                external_id="db-uuid-foreign",
                display_name="Foreign DB",
            )
        )


def _login(client, email: str = "owner@db.test", password: str = "db-password") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_provision_database_creates_tenant_resource(client, monkeypatch):
    """POST /api/v1/databases provisions a DB and creates a TenantResource for the caller's tenant."""
    asyncio.run(_seed_db_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    provisioned: list[dict] = []

    async def fake_provision(self, db_type, server_uuid, project_uuid, environment_name, name, **opts):
        provisioned.append({"db_type": db_type, "name": name})
        return {"uuid": "new-db-uuid-123", "name": name}

    monkeypatch.setattr(CoolifyClient, "provision_database", fake_provision)

    headers = _login(client)
    response = client.post(
        "/api/v1/databases",
        headers=headers,
        json={
            "db_type": "postgresql",
            "name": "my-postgres",
            "server_uuid": "srv-123",
            "project_uuid": "proj-456",
            "environment_name": "production",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True

    # New DB must appear in GET /api/v1/databases for this tenant.
    async def fake_list_databases(self, refresh=False):
        from app.services.coolify import CoolifyDatabase
        return [CoolifyDatabase(id="new-db-uuid-123", name="my-postgres", status="running")]

    monkeypatch.setattr(CoolifyClient, "list_databases", fake_list_databases)

    listed = client.get("/api/v1/databases", headers=headers)
    assert listed.status_code == 200
    assert any(db["id"] == "new-db-uuid-123" for db in listed.json())

    # TenantResource row was created with resource_type=database
    async def check_resource():
        from sqlalchemy import func, select
        async with session_scope() as session:
            from app.models import Tenant as T
            tenant = (await session.scalars(select(T).where(T.slug == "dbt"))).first()
            count = await session.scalar(
                select(func.count()).select_from(TenantResource).where(
                    TenantResource.tenant_id == tenant.id,
                    TenantResource.resource_type == RESOURCE_TYPE_DATABASE,
                    TenantResource.external_id == "new-db-uuid-123",
                )
            )
            return count or 0

    assert asyncio.run(check_resource()) == 1, "Expected a TenantResource(database) row to be created"


def test_provision_database_blocked_when_actions_disabled(client, monkeypatch):
    """POST /api/v1/databases with ENABLE_PROVIDER_ACTIONS=false → 403, no Coolify call."""
    asyncio.run(_seed_db_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", False)

    called: list[bool] = []

    async def fake_provision(self, db_type, server_uuid, project_uuid, environment_name, name, **opts):
        called.append(True)
        return {"uuid": "should-not-reach", "name": name}

    monkeypatch.setattr(CoolifyClient, "provision_database", fake_provision)

    headers = _login(client)
    response = client.post(
        "/api/v1/databases",
        headers=headers,
        json={
            "db_type": "postgresql",
            "name": "blocked-db",
            "server_uuid": "srv-123",
            "project_uuid": "proj-456",
            "environment_name": "production",
        },
    )
    assert response.status_code == 403, response.text
    assert called == [], "CoolifyClient.provision_database must NOT be called when actions are disabled"


def test_provision_database_invalid_db_type_returns_422(client, monkeypatch):
    """POST /api/v1/databases with an unsupported db_type → 422."""
    asyncio.run(_seed_db_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    headers = _login(client)
    response = client.post(
        "/api/v1/databases",
        headers=headers,
        json={
            "db_type": "oracle",  # not in the allow-list
            "name": "my-oracle",
            "server_uuid": "srv-123",
            "project_uuid": "proj-456",
            "environment_name": "production",
        },
    )
    assert response.status_code == 422, response.text


def test_backups_tenant_isolation(client, monkeypatch):
    """GET /api/v1/databases/{uuid}/backups for a foreign db_uuid → 403."""
    asyncio.run(_seed_db_tenant())
    asyncio.run(_seed_other_tenant())

    async def fake_list_backups(self, uuid):
        return [{"id": "backup-1", "frequency": "0 2 * * *"}]

    monkeypatch.setattr(CoolifyClient, "list_database_backups", fake_list_backups)

    headers = _login(client)
    # Tenant owns "db-uuid-existing", tries to access "db-uuid-foreign"
    response = client.get("/api/v1/databases/db-uuid-foreign/backups", headers=headers)
    assert response.status_code in (403, 404), response.text


def test_create_backup_on_owned_database(client, monkeypatch):
    """POST /api/v1/databases/{uuid}/backups on the tenant's own db → 200."""
    asyncio.run(_seed_db_tenant())
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    created: list[dict] = []

    async def fake_create_backup(self, uuid, **config):
        created.append({"uuid": uuid, "config": config})
        return {"id": "backup-cfg-1", "frequency": config.get("frequency", "0 2 * * *")}

    monkeypatch.setattr(CoolifyClient, "create_database_backup", fake_create_backup)

    headers = _login(client)
    response = client.post(
        "/api/v1/databases/db-uuid-existing/backups",
        headers=headers,
        json={"frequency": "0 2 * * *", "retention_days": 7},
    )
    assert response.status_code == 200, response.text
    assert created and created[0]["uuid"] == "db-uuid-existing"
```

- [ ] **Step 2: Run to confirm all 5 tests FAIL**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m pytest tests/test_databases_api.py -v 2>&1 | tail -20
```

Expected: All 5 tests FAIL with `ImportError` or `404` (routes don't exist yet).

- [ ] **Step 3: Add `DB_TYPE_ALLOWLIST`, `provision_database`, and `get_database` to `CoolifyClient`**

In `app/services/coolify.py`, add immediately after the `RESOURCE_TYPE_DATABASE` import block at the top (after the existing module-level code but before the `CoolifyApplication` class). Add this constant:

```python
# At module level, after imports
DB_TYPE_ALLOWLIST: frozenset[str] = frozenset({
    "postgresql", "mysql", "mariadb", "mongodb",
    "redis", "keydb", "dragonfly", "clickhouse",
})
```

Then in `CoolifyClient`, add these two methods after `restart_database` (after line ~844):

```python
    async def provision_database(
        self,
        db_type: str,
        server_uuid: str,
        project_uuid: str,
        environment_name: str,
        name: str,
        **opts: Any,
    ) -> dict[str, Any]:
        """Provision a new managed database on Coolify.

        Coolify uses type-specific POST endpoints:
        POST /api/v1/databases/{postgresql|mysql|mariadb|mongodb|redis|keydb|dragonfly|clickhouse}

        Required fields per v4 spec: server_uuid, project_uuid, environment_name, name.
        """
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        body: dict[str, Any] = {
            "server_uuid": server_uuid,
            "project_uuid": project_uuid,
            "environment_name": environment_name,
            "name": name,
            **opts,
        }
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="POST",
            url=f"{self.base_url}/api/v1/databases/{db_type}",
            headers=self.headers(),
            json_body=body,
        )
        await self.cache.delete("coolify:databases")
        return payload if isinstance(payload, dict) else {"ok": True, "payload": payload}

    async def list_database_backups(self, database_uuid: str) -> list[dict[str, Any]]:
        """List scheduled backup configs for a database (GET /databases/{uuid}/backups)."""
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}/backups",
            headers=self.headers(),
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data", [])
        return []

    async def create_database_backup(self, database_uuid: str, **config: Any) -> dict[str, Any]:
        """Create a backup config for a database (POST /databases/{uuid}/backups).

        Common config fields per v4 spec:
        - frequency: cron string (e.g. "0 2 * * *")
        - retention_days: int
        - s3_storage_id: str (UUID of pre-configured S3 storage)
        """
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="POST",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}/backups",
            headers=self.headers(),
            json_body=config,
        )
        return payload if isinstance(payload, dict) else {"ok": True}
```

Note: `get_database` already exists in `CoolifyClient` at line ~802. Do NOT re-add it.

- [ ] **Step 4: Run ruff**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m ruff check app/services/coolify.py
```

Expected: No output (clean).

- [ ] **Step 5: Commit**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && git add app/services/coolify.py tests/test_databases_api.py && git commit -m "feat(databases): add provision_database + backup methods to CoolifyClient (RED tests)"
```

---

## Task 2: Pydantic Contracts — `DatabaseSummary`, `DatabaseProvisionRequest`, `BackupConfigSummary`, `BackupCreateRequest`

**Files:**
- Modify: `app/api/contracts.py` (append to end of file)

**Interfaces:**
- Produces:
  - `class DatabaseSummary(BaseModel)` with fields: `id: str`, `name: str`, `type: str = ""`, `status: str = "unknown"`, `internal_db_url: str = ""`, `image: str = ""`
  - `class DatabaseProvisionRequest(BaseModel)` with fields: `db_type: str`, `name: str`, `server_uuid: str`, `project_uuid: str`, `environment_name: str`
  - `class BackupConfigSummary(BaseModel)` with fields: `id: str`, `frequency: str = ""`, `retention_days: int = 0`, `s3_storage_id: str = ""`
  - `class BackupCreateRequest(BaseModel)` with fields: `frequency: str = "0 2 * * *"`, `retention_days: int = 7`, `s3_storage_id: str = ""`

- [ ] **Step 1: Append contracts to `app/api/contracts.py`**

Add these four classes at the end of `app/api/contracts.py`:

```python
class DatabaseSummary(BaseModel):
    id: str
    name: str
    type: str = ""
    status: str = "unknown"
    internal_db_url: str = ""
    image: str = ""


class DatabaseProvisionRequest(BaseModel):
    """Request to provision a new managed database via Coolify.

    db_type must be one of the Coolify-supported database types.
    No tenant_id, role, or owner fields — tenant is always the caller's tenant.
    """
    db_type: str = Field(..., description="One of: postgresql, mysql, mariadb, mongodb, redis, keydb, dragonfly, clickhouse")
    name: str = Field(..., min_length=1, max_length=120)
    server_uuid: str
    project_uuid: str
    environment_name: str


class BackupConfigSummary(BaseModel):
    id: str
    frequency: str = ""
    retention_days: int = 0
    s3_storage_id: str = ""


class BackupCreateRequest(BaseModel):
    frequency: str = "0 2 * * *"
    retention_days: int = 7
    s3_storage_id: str = ""
```

- [ ] **Step 2: Verify import works**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -c "from app.api.contracts import DatabaseSummary, DatabaseProvisionRequest, BackupConfigSummary, BackupCreateRequest; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run ruff**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m ruff check app/api/contracts.py
```

Expected: No output (clean).

- [ ] **Step 4: Commit**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && git add app/api/contracts.py && git commit -m "feat(databases): add database API contracts (DatabaseSummary, provision, backup)"
```

---

## Task 3: `DatabasesService` — provision + backup methods

**Files:**
- Modify: `app/modules/databases/service.py`

**Interfaces:**
- Consumes from Task 1:
  - `CoolifyClient.provision_database(db_type, server_uuid, project_uuid, environment_name, name, **opts) -> dict[str, Any]`
  - `CoolifyClient.list_database_backups(database_uuid) -> list[dict[str, Any]]`
  - `CoolifyClient.create_database_backup(database_uuid, **config) -> dict[str, Any]`
  - `DB_TYPE_ALLOWLIST: frozenset[str]` from `app.services.coolify`
- Produces:
  - `async def _ensure_database_access(self, session, tenant_id, db_uuid) -> None`
  - `async def provision_for_tenant(self, session, tenant_id, db_type, name, server_uuid, project_uuid, environment_name) -> dict[str, Any]`
  - `async def backups_for_tenant(self, session, tenant_id, db_uuid) -> list[dict[str, Any]]`
  - `async def create_backup_for_tenant(self, session, tenant_id, db_uuid, **config) -> dict[str, Any]`

- [ ] **Step 1: Rewrite `app/modules/databases/service.py`**

Replace the entire content of `app/modules/databases/service.py` with:

```python
"""Databases service — tenant-scoped wrappers around the Coolify databases API."""

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import TenantResource
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_DATABASE
from app.services.coolify import CoolifyClient, CoolifyDatabase, DB_TYPE_ALLOWLIST
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter


class DatabasesService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CoolifyClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )
        self.actions_enabled = get_settings().enable_provider_actions

    def _require_actions(self) -> None:
        if not self.actions_enabled:
            raise ProviderAPIError(
                service="Coolify",
                message="Provider actions are disabled (ENABLE_PROVIDER_ACTIONS=false).",
                status_code=403,
            )

    async def _ensure_database_access(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        db_uuid: str,
    ) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_COOLIFY,
            resource_type=RESOURCE_TYPE_DATABASE,
            external_id=db_uuid,
        )
        if not allowed:
            raise ProviderAPIError(
                service="Coolify",
                message="Database is not assigned to this tenant.",
                status_code=403,
            )

    async def list_databases(self, refresh: bool = False) -> list[CoolifyDatabase]:
        return await self.client.list_databases()

    async def list_databases_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        refresh: bool = False,
    ) -> list[CoolifyDatabase]:
        databases = await self.list_databases(refresh=refresh)
        return await TenantResourceFilter(session, tenant_id).filter_databases(databases)

    async def provision_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        db_type: str,
        name: str,
        server_uuid: str,
        project_uuid: str,
        environment_name: str,
    ) -> dict[str, Any]:
        """Provision a new managed database via Coolify and record it as a TenantResource.

        Steps:
        1. Gate on ENABLE_PROVIDER_ACTIONS (raises ProviderAPIError 403 if disabled).
        2. Validate db_type against DB_TYPE_ALLOWLIST (raises ValueError if invalid — caller maps to 422).
        3. Call Coolify: POST /api/v1/databases/{db_type}.
        4. On success, create TenantResource(provider=coolify, resource_type=database, external_id=<uuid>).
        5. On Coolify failure, ProviderAPIError propagates (no TenantResource created).
        """
        self._require_actions()

        if db_type not in DB_TYPE_ALLOWLIST:
            raise ValueError(
                f"Unsupported db_type '{db_type}'. "
                f"Supported types: {', '.join(sorted(DB_TYPE_ALLOWLIST))}"
            )

        result = await self.client.provision_database(
            db_type=db_type,
            server_uuid=server_uuid,
            project_uuid=project_uuid,
            environment_name=environment_name,
            name=name,
        )

        # Extract the new database's UUID from the Coolify response.
        # Coolify v4 returns {"uuid": "...", "name": "..."} on creation.
        db_uuid = str(result.get("uuid") or result.get("id") or "")
        if db_uuid:
            resource = TenantResource(
                tenant_id=tenant_id or "",
                provider=PROVIDER_COOLIFY,
                resource_type=RESOURCE_TYPE_DATABASE,
                external_id=db_uuid,
                display_name=name,
            )
            session.add(resource)
            await session.flush()

        result.setdefault("ok", True)
        return result

    async def backups_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        db_uuid: str,
    ) -> list[dict[str, Any]]:
        """List backup configs for a tenant-owned database."""
        await self._ensure_database_access(session, tenant_id, db_uuid)
        return await self.client.list_database_backups(db_uuid)

    async def create_backup_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        db_uuid: str,
        **config: Any,
    ) -> dict[str, Any]:
        """Create a backup config for a tenant-owned database."""
        self._require_actions()
        await self._ensure_database_access(session, tenant_id, db_uuid)
        return await self.client.create_database_backup(db_uuid, **config)
```

- [ ] **Step 2: Verify import**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -c "from app.modules.databases.service import DatabasesService; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run ruff**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m ruff check app/modules/databases/service.py
```

Expected: No output (clean).

- [ ] **Step 4: Commit**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && git add app/modules/databases/service.py && git commit -m "feat(databases): DatabasesService.provision_for_tenant + backup methods"
```

---

## Task 4: `/api/v1/databases` Route Handlers

**Files:**
- Modify: `app/api/routes.py`

**Interfaces:**
- Consumes from Task 2:
  - `DatabaseSummary`, `DatabaseProvisionRequest`, `BackupConfigSummary`, `BackupCreateRequest`
- Consumes from Task 3:
  - `DatabasesService` with `list_databases_for_tenant`, `provision_for_tenant`, `backups_for_tenant`, `create_backup_for_tenant`

- [ ] **Step 1: Add import of new contracts and `DatabasesService` to `app/api/routes.py`**

In `app/api/routes.py`, at the top where contracts are imported (around line 9), add to the import block from `app.api.contracts`:

```python
from app.api.contracts import (
    AdminResponse,
    AdminSummary,
    AppActionResponse,
    AppInstallRequest,
    AppTemplateSummary,
    AuthResponse,
    BackupConfigSummary,
    BackupCreateRequest,
    CachePurgeRequest,
    DatabaseProvisionRequest,
    DatabaseSummary,
    DashboardMetrics,
    DashboardResponse,
    DeploymentDetail,
    DeploymentLogLine,
    DeploymentStatus,
    DeployStartResponse,
    DNSRecordCreateRequest,
    DNSRecordSummary,
    DNSResponse,
    DNSZoneSummary,
    DnsExportResponse,
    DnsImportRequest,
    DnssecUpdateRequest,
    EnvVarCreateRequest,
    GitDeployRequest,
    InstalledAppSummary,
    MailboxSummary,
    MailDomainSummary,
    MailResponse,
    PlanCreateRequest,
    PlanSummary,
    PlanUpdateRequest,
    ProviderSummary,
    SignupRequest,
    SiteActionResponse,
    SiteDeploymentSummary,
    SiteSummary,
    TenantAdminCreateRequest,
    TenantCreateRequest,
    TenantResourceCreateRequest,
    TenantResourceSummary,
    TenantSummary,
    UsageResponse,
    ZoneAnalytics,
    ZoneAnalyticsPoint,
    ZoneAnalyticsTotals,
    ZoneSettings,
    ZoneSettingUpdateRequest,
)
```

Also add `DatabasesService` to the service imports (after `from app.modules.sites.service import SitesService`):

```python
from app.modules.databases.service import DatabasesService
```

- [ ] **Step 2: Add the 4 route handlers at the end of `app/api/routes.py`** (before the closing of the file, after the `/api/v1/usage` endpoint):

```python
# ---------------------------------------------------------------------------
# Databases endpoints  (/api/v1/databases)
# ---------------------------------------------------------------------------

@router.get("/databases", response_model=list[DatabaseSummary])
async def api_list_databases(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DatabaseSummary]:
    """List Coolify databases assigned to the caller's tenant."""
    service = DatabasesService(request)
    databases = await service.list_databases_for_tenant(
        session,
        current_admin.tenant_id,
        refresh=request.query_params.get("refresh") == "1",
    )
    return [
        DatabaseSummary(
            id=db.id,
            name=db.name,
            type=db.type,
            status=db.status,
            internal_db_url=db.internal_db_url,
            image=db.image,
        )
        for db in databases
    ]


@router.post("/databases", response_model=SiteActionResponse)
async def api_provision_database(
    payload: DatabaseProvisionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    """Provision a new managed database via Coolify (tenant-scoped).

    Gated by ENABLE_PROVIDER_ACTIONS. db_type must be in the supported allow-list.
    """
    service = DatabasesService(request)
    try:
        result = await service.provision_for_tenant(
            session,
            current_admin.tenant_id,
            db_type=payload.db_type,
            name=payload.name,
            server_uuid=payload.server_uuid,
            project_uuid=payload.project_uuid,
            environment_name=payload.environment_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(
        ok=bool(result.get("ok", True)),
        message=str(result.get("message", "Database provisioned.")),
    )


@router.get("/databases/{db_uuid}/backups", response_model=list[BackupConfigSummary])
async def api_list_database_backups(
    db_uuid: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[BackupConfigSummary]:
    """List backup configs for a tenant-owned database."""
    service = DatabasesService(request)
    try:
        backups = await service.backups_for_tenant(session, current_admin.tenant_id, db_uuid)
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return [
        BackupConfigSummary(
            id=str(b.get("uuid") or b.get("id") or ""),
            frequency=str(b.get("frequency") or ""),
            retention_days=int(b.get("retention_days") or b.get("retention") or 0),
            s3_storage_id=str(b.get("s3_storage_id") or ""),
        )
        for b in backups
    ]


@router.post("/databases/{db_uuid}/backups", response_model=SiteActionResponse)
async def api_create_database_backup(
    db_uuid: str,
    payload: BackupCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> SiteActionResponse:
    """Create a backup config for a tenant-owned database. Gated by ENABLE_PROVIDER_ACTIONS."""
    service = DatabasesService(request)
    config: dict[str, object] = {
        "frequency": payload.frequency,
        "retention_days": payload.retention_days,
    }
    if payload.s3_storage_id:
        config["s3_storage_id"] = payload.s3_storage_id
    try:
        result = await service.create_backup_for_tenant(
            session, current_admin.tenant_id, db_uuid, **config
        )
    except ProviderAPIError as exc:
        status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return SiteActionResponse(
        ok=bool(result.get("ok", True)),
        message=str(result.get("message", "Backup config created.")),
    )
```

- [ ] **Step 3: Verify app starts**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -c "from app.main import create_app; app = create_app(); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run ruff**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m ruff check app/api/routes.py
```

Expected: No output (clean).

- [ ] **Step 5: Commit**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && git add app/api/routes.py && git commit -m "feat(databases): /api/v1/databases route handlers (list, provision, backups)"
```

---

## Task 5: Go Green — Run Tests and Fix

**Files:**
- Modify: `tests/test_databases_api.py` (minor fixes if needed)
- Possibly: `app/api/routes.py`, `app/modules/databases/service.py`

- [ ] **Step 1: Run the database API tests**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m pytest tests/test_databases_api.py -v 2>&1 | tail -30
```

Expected: All 5 tests PASS.

If any fail, investigate and fix before continuing. Common issues:
- Import order in `routes.py` (ruff may flag alphabetical sort issues in the contracts import)
- The `status_code` variable shadowing the FastAPI `status` import in route handlers — use `exc.status_code or status.HTTP_502_BAD_GATEWAY` but assign to a local name like `_status_code` to avoid shadowing:

```python
    except ProviderAPIError as exc:
        _status_code = exc.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=_status_code, detail=str(exc)) from exc
```

- `DatabasesService` reads `enable_provider_actions` at `__init__` time; the monkeypatch must run before the service is instantiated. The monkeypatch on `get_settings()` object works because `get_settings()` is a cached singleton — verify `get_settings()` is used consistently.

- [ ] **Step 2: Run full test suite**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m pytest -q 2>&1 | tail -10
```

Expected: `188 passed` (183 existing + 5 new), 0 errors.

- [ ] **Step 3: Run ruff over entire project**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && python -m ruff check . 2>&1 | head -30
```

Expected: No output (clean).

- [ ] **Step 4: Commit GREEN state**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && git add -p && git commit -m "test(databases): all 5 database API tests GREEN (provision, gate, isolation, backups)"
```

---

## Task 6: Write Task Report

**Files:**
- Create: `/Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host/.superpowers/sdd/task-g4-report.md`

- [ ] **Step 1: Create `.superpowers/sdd/` directory**

```bash
mkdir -p /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host/.superpowers/sdd
```

- [ ] **Step 2: Write report**

Write a report to `/Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host/.superpowers/sdd/task-g4-report.md` covering:

1. **Verified Coolify v4 Endpoints Used** (and any discrepancy vs research sketch)
2. **CoolifyClient methods added** (signatures)
3. **DatabasesService provision + backup flow** (including isolation guard + actions gate)
4. **`/api/v1` endpoints added** (method + path + contract)
5. **`db_type` allow-list** (the 8 types)
6. **RED/GREEN test summary** (5 tests, what each covers)
7. **Full-suite test count** (before and after)
8. **ruff status**

Report template:

```markdown
# Task G4 — Coolify DB Provisioning + Backups

**Date:** 2026-06-30  
**Branch:** feat/post-deploy-followups  
**Commit:** <fill in SHA and subject>

## Verified Coolify v4 Endpoints

All endpoints confirmed from research doc (openapi.json source):

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/databases/{db_type}` | Type-specific create; required: server_uuid, project_uuid, environment_name, name |
| GET | `/api/v1/databases/{uuid}` | Already existed in CoolifyClient |
| GET | `/api/v1/databases/{uuid}/backups` | List backup configs |
| POST | `/api/v1/databases/{uuid}/backups` | Create backup config |

**No discrepancy** vs research sketch — endpoints match the documented v4 spec exactly.

## CoolifyClient Methods Added (`app/services/coolify.py`)

- `provision_database(db_type, server_uuid, project_uuid, environment_name, name, **opts) -> dict[str, Any]`
  - POST to `/api/v1/databases/{db_type}` (type-specific path)
  - Invalidates `coolify:databases` cache on success
- `list_database_backups(database_uuid) -> list[dict[str, Any]]`
  - GET `/api/v1/databases/{uuid}/backups`
- `create_database_backup(database_uuid, **config) -> dict[str, Any]`
  - POST `/api/v1/databases/{uuid}/backups`

**Note:** `get_database` already existed; not duplicated.

**`DB_TYPE_ALLOWLIST`** (module-level constant):
`{"postgresql", "mysql", "mariadb", "mongodb", "redis", "keydb", "dragonfly", "clickhouse"}`

## DatabasesService Flow (`app/modules/databases/service.py`)

**provision_for_tenant:**
1. `_require_actions()` → raises ProviderAPIError(403) if ENABLE_PROVIDER_ACTIONS=false
2. Validate `db_type` in `DB_TYPE_ALLOWLIST` → raises ValueError (mapped to 422 in route)
3. `client.provision_database(...)` → POST to Coolify
4. Extract `uuid` from response → create `TenantResource(provider=coolify, resource_type=database, external_id=uuid)`
5. On Coolify failure, ProviderAPIError propagates (no TenantResource created)

**_ensure_database_access:**
- Queries `TenantResourceFilter.is_resource_accessible(provider=coolify, resource_type=database, external_id=db_uuid)`
- Raises ProviderAPIError(403) if not found → tenant isolation enforced

**backups_for_tenant:** `_ensure_database_access` then `client.list_database_backups`
**create_backup_for_tenant:** `_require_actions` + `_ensure_database_access` then `client.create_database_backup`

## `/api/v1` Endpoints Added (`app/api/routes.py`)

| Method | Path | Contract | Gate |
|---|---|---|---|
| GET | `/api/v1/databases` | `list[DatabaseSummary]` | auth |
| POST | `/api/v1/databases` | `DatabaseProvisionRequest` → `SiteActionResponse` | auth + ENABLE_PROVIDER_ACTIONS |
| GET | `/api/v1/databases/{db_uuid}/backups` | `list[BackupConfigSummary]` | auth + tenant ownership |
| POST | `/api/v1/databases/{db_uuid}/backups` | `BackupCreateRequest` → `SiteActionResponse` | auth + ENABLE_PROVIDER_ACTIONS + tenant ownership |

## db_type Allow-List

User-supplied `db_type` is validated against `DB_TYPE_ALLOWLIST` before being interpolated into the URL path. Unknown types raise `ValueError` → 422. This prevents arbitrary path construction from user input.

## RED/GREEN Tests (`tests/test_databases_api.py`)

| Test | What it covers |
|---|---|
| `test_provision_database_creates_tenant_resource` | Provision → calls CoolifyClient, creates TenantResource, new DB appears in list |
| `test_provision_database_blocked_when_actions_disabled` | 403 when ENABLE_PROVIDER_ACTIONS=false, no Coolify call |
| `test_provision_database_invalid_db_type_returns_422` | 422 for unsupported db_type |
| `test_backups_tenant_isolation` | Foreign db_uuid → 403 (other tenant's database not accessible) |
| `test_create_backup_on_owned_database` | 200 on tenant's own db, Coolify backup method called |

All 5 tests were written BEFORE implementation (RED), then implementation made them GREEN.

## Test Suite

- Before: 183 tests collected
- After: 188 tests collected (183 + 5 new)
- Result: 188 passed, 0 errors

## ruff

`ruff check .` — clean (no errors)
```

- [ ] **Step 3: Create squash commit with final message**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && git add .superpowers/sdd/task-g4-report.md && git commit -m "feat(databases): Coolify DB provisioning + backups (/api/v1/databases, tenant-scoped)"
```

---

## Self-Review

**Spec coverage check:**

- [x] `CoolifyClient.provision_database` — Task 1
- [x] `CoolifyClient.list_database_backups` — Task 1
- [x] `CoolifyClient.create_database_backup` — Task 1
- [x] `get_database` — already exists in CoolifyClient, spec says "add it" — confirmed it exists, no duplicate needed
- [x] `DatabasesService.provision_for_tenant` — Task 3
- [x] `DatabasesService.backups_for_tenant` — Task 3
- [x] `DatabasesService.create_backup_for_tenant` — Task 3
- [x] `_ensure_database_access` — Task 3
- [x] `GET /api/v1/databases` — Task 4
- [x] `POST /api/v1/databases` — Task 4
- [x] `GET /api/v1/databases/{uuid}/backups` — Task 4
- [x] `POST /api/v1/databases/{uuid}/backups` — Task 4
- [x] `DatabaseSummary` contract — Task 2
- [x] `DatabaseProvisionRequest` — Task 2
- [x] `BackupConfigSummary` — Task 2
- [x] `BackupCreateRequest` — Task 2
- [x] db_type allow-list + safe path construction — Task 1 + Task 3
- [x] ENABLE_PROVIDER_ACTIONS gate on writes — Task 3 (`_require_actions`) + tests
- [x] Tenant isolation: `_ensure_database_access` — Task 3 + `test_backups_tenant_isolation`
- [x] No tenant_id/role/owner fields in request bodies — contracts don't have them
- [x] TDD: tests written RED first (Task 1 step 1), then go GREEN (Task 5)
- [x] Report written to `.superpowers/sdd/task-g4-report.md` — Task 6

**Placeholder scan:** None found.

**Type consistency:**
- `db_type` used consistently (not `database_type`)
- `db_uuid` as parameter name in service + route handler
- `DatabasesService` class name matches what routes.py imports
- `DB_TYPE_ALLOWLIST` constant name used in both `coolify.py` and `databases/service.py`
- `BackupConfigSummary` — `id` field: routes.py extracts `b.get("uuid") or b.get("id")` — consistent with Coolify's typical `uuid` response field
