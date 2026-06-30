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
    """POST /api/v1/databases with ENABLE_PROVIDER_ACTIONS=false -> 403, no Coolify call."""
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
    """POST /api/v1/databases with an unsupported db_type -> 422."""
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
    """GET /api/v1/databases/{uuid}/backups for a foreign db_uuid -> 403."""
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
    """POST /api/v1/databases/{uuid}/backups on the tenant's own db -> 200."""
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
