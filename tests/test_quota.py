"""Task 3.2: QuotaService — usage + atomic check_and_reserve + release.

RED → GREEN sequence (run with pytest -q tests/test_quota.py).
"""

import asyncio

import pytest

from app.db import session_scope
from app.db.session import init_db
from app.models import Deployment, Plan, Tenant, TenantResource
from app.models.deployment import STATUS_BUILDING, STATUS_QUEUED
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services.quota import Allocation, QuotaExceeded, QuotaService


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

TENANT_ID: str = ""
PLAN_ID: str = ""


async def _seed() -> tuple[str, str]:
    """Seed a plan with max_apps=1 and a tenant assigned to it."""
    await init_db()
    async with session_scope() as session:
        plan = Plan(
            key="quota_test_plan",
            name="Quota Test",
            max_apps=1,
            max_domains=0,
            cpu_millicores=500,
            mem_mb=512,
            disk_mb=2048,
        )
        session.add(plan)
        await session.flush()

        tenant = Tenant(name="Quota Tenant", slug="quota-tenant", status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()

        return tenant.id, plan.id


async def _seed_deployment(tenant_id: str, project: str, status: str) -> None:
    """Seed a Deployment row with the given status."""
    async with session_scope() as session:
        dep = Deployment(
            tenant_id=tenant_id,
            project=project,
            status=status,
        )
        session.add(dep)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestQuotaReserveAndRelease:
    """check_and_reserve / release lifecycle."""

    def setup_method(self):
        self.tenant_id, self.plan_id = asyncio.run(_seed())

    def test_first_reserve_succeeds(self):
        """Reserving app#1 under a max_apps=1 plan must succeed and insert a TenantResource."""

        async def run():
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                await svc.check_and_reserve("app1", alloc, "App One")
            # Verify the row was committed.
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 1

        asyncio.run(run())

    def test_second_reserve_raises_quota_exceeded(self):
        """Reserving a second app when max_apps=1 must raise QuotaExceeded."""

        async def run():
            # Reserve first app.
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                await svc.check_and_reserve("app1", alloc, "App One")

            # Second reserve must raise.
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                with pytest.raises(QuotaExceeded) as exc_info:
                    await svc.check_and_reserve("app2", alloc, "App Two")

            exc = exc_info.value
            assert exc.reason == "apps"
            assert exc.limit == 1
            assert exc.used == 1
            assert exc.error == "quota_exceeded"

        asyncio.run(run())

    def test_release_removes_row_and_allows_new_reserve(self):
        """release() removes the reservation so a subsequent reserve succeeds."""

        async def run():
            # Reserve.
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                await svc.check_and_reserve("app1", alloc, "App One")

            # Release.
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                await svc.release("app1")

            # Now a new reserve for "app2" should succeed.
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                await svc.check_and_reserve("app2", alloc, "App Two")

            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 1  # app2 now exists, app1 was released

        asyncio.run(run())


class TestQuotaUsage:
    """usage() accurately reflects TenantResource rows + in-flight Deployment rows."""

    def setup_method(self):
        self.tenant_id, self.plan_id = asyncio.run(_seed())

    def test_usage_empty(self):
        async def run():
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u == {"apps": 0, "cpu_millicores": 0, "mem_mb": 0, "disk_mb": 0}

        asyncio.run(run())

    def test_usage_counts_reserved_app_resources(self):
        """usage() sums cpu/mem/disk from reservation rows."""

        async def run():
            async with session_scope() as session:
                session.add(
                    TenantResource(
                        tenant_id=self.tenant_id,
                        provider=PROVIDER_DOCKER,
                        resource_type=RESOURCE_TYPE_APP,
                        external_id="app-x",
                        display_name="App X",
                        cpu_millicores=250,
                        mem_mb=256,
                        disk_mb=512,
                    )
                )

            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 1
                assert u["cpu_millicores"] == 250
                assert u["mem_mb"] == 256
                assert u["disk_mb"] == 512

        asyncio.run(run())

    def test_usage_counts_inflight_deployment_queued(self):
        """In-flight Deployments with status 'queued' count toward apps."""

        async def run():
            await _seed_deployment(self.tenant_id, "dep-q", STATUS_QUEUED)
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 1

        asyncio.run(run())

    def test_usage_counts_inflight_deployment_building(self):
        """In-flight Deployments with status 'building' count toward apps."""

        async def run():
            await _seed_deployment(self.tenant_id, "dep-b", STATUS_BUILDING)
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 1

        asyncio.run(run())

    def test_usage_coalesces_null_columns_to_config_defaults(self):
        """NULL cpu/mem/disk in TenantResource rows fall back to config defaults."""
        from app.config import get_settings

        cfg = get_settings()

        async def run():
            async with session_scope() as session:
                session.add(
                    TenantResource(
                        tenant_id=self.tenant_id,
                        provider=PROVIDER_DOCKER,
                        resource_type=RESOURCE_TYPE_APP,
                        external_id="app-null",
                        display_name="Null App",
                        cpu_millicores=None,
                        mem_mb=None,
                        disk_mb=None,
                    )
                )

            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["cpu_millicores"] == cfg.default_app_cpu_millicores
                assert u["mem_mb"] == cfg.default_app_mem_mb
                assert u["disk_mb"] == cfg.default_app_disk_mb

        asyncio.run(run())

    def test_usage_combined_resources_and_inflight(self):
        """usage() adds TenantResource app count + in-flight Deployment count (distinct projects)."""

        async def run():
            # Seed 1 TenantResource app and 1 in-flight deployment for a DIFFERENT project.
            async with session_scope() as session:
                session.add(
                    TenantResource(
                        tenant_id=self.tenant_id,
                        provider=PROVIDER_DOCKER,
                        resource_type=RESOURCE_TYPE_APP,
                        external_id="app-combined",
                        display_name="Combined",
                        cpu_millicores=500,
                        mem_mb=512,
                        disk_mb=1024,
                    )
                )

            await _seed_deployment(self.tenant_id, "dep-combined", STATUS_BUILDING)

            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 2

        asyncio.run(run())


async def _seed_max2() -> tuple[str, str]:
    """Seed a plan with max_apps=2 and a tenant assigned to it."""
    await init_db()
    async with session_scope() as session:
        plan = Plan(
            key="quota_test_plan_2",
            name="Quota Test 2",
            max_apps=2,
            max_domains=0,
            cpu_millicores=500,
            mem_mb=512,
            disk_mb=2048,
        )
        session.add(plan)
        await session.flush()

        tenant = Tenant(name="Quota Tenant 2", slug="quota-tenant-2", status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()

        return tenant.id, plan.id


class TestQuotaDedup:
    """De-duplication: a project with both a TenantResource reservation AND an in-flight
    Deployment must be counted ONCE, not twice."""

    def setup_method(self):
        self.tenant_id, self.plan_id = asyncio.run(_seed_max2())

    def test_reserved_app_with_inflight_deploy_counts_once(self):
        """An app that has a TenantResource reservation AND an in-flight Deployment
        for the same project must not be double-counted in usage()."""

        async def run():
            # Reserve "app1" (creates TenantResource with external_id="app1").
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                await svc.check_and_reserve("app1", alloc, "App One")

            # Seed an in-flight Deployment for the SAME project "app1".
            await _seed_deployment(self.tenant_id, "app1", STATUS_BUILDING)

            # Must count as 1 (not 2) — reservation is authoritative.
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 1, f"Expected 1 (de-duped), got {u['apps']}"

        asyncio.run(run())

    def test_reserved_app_with_inflight_does_not_block_second_reserve(self):
        """With max_apps=2: reserving app1 + an in-flight deploy for app1 must NOT
        prevent reserving a distinct app2 (the first slot must not be double-counted)."""

        async def run():
            # Reserve "app1".
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                await svc.check_and_reserve("app1", alloc, "App One")

            # Seed an in-flight Deployment for the SAME project "app1".
            await _seed_deployment(self.tenant_id, "app1", STATUS_BUILDING)

            # Reserving "app2" must succeed — only 1 slot used (not 2).
            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                alloc = Allocation(cpu_millicores=500, mem_mb=512, disk_mb=1024)
                await svc.check_and_reserve("app2", alloc, "App Two")

        asyncio.run(run())

    def test_inflight_deploy_without_reservation_still_counts(self):
        """An in-flight Deployment for a project with NO TenantResource reservation
        must still be counted (safety-net path preserved)."""

        async def run():
            # Only a Deployment, no TenantResource.
            await _seed_deployment(self.tenant_id, "new-app", STATUS_QUEUED)

            async with session_scope() as session:
                svc = QuotaService(session, self.tenant_id)
                u = await svc.usage()
                assert u["apps"] == 1, f"Expected 1 (unresered in-flight), got {u['apps']}"

        asyncio.run(run())
