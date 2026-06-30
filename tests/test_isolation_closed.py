"""Task 2.1: Verify that TenantResourceFilter is deny-by-default.

A tenant with is_platform_scope=False and zero TenantResource rows must be
denied access to every resource. A tenant with is_platform_scope=True and zero
rows must still see everything (fall-open for platform-scope only).
"""

import asyncio

from app.db import session_scope
from app.models import Tenant
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    RESOURCE_TYPE_DNS_ZONE,
)
from app.services.cloudflare import CloudflareZone
from app.services.tenant_resources import TenantResourceFilter


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

_CUST_SLUG = "cust"
_PLATFORM_SLUG = "plat"


async def _seed_tenants() -> tuple[str, str]:
    """Return (cust_tenant_id, platform_tenant_id)."""
    async with session_scope() as session:
        cust = Tenant(name="Customer Tenant", slug=_CUST_SLUG, status="active", is_platform_scope=False)
        plat = Tenant(name="Platform Tenant", slug=_PLATFORM_SLUG, status="active", is_platform_scope=True)
        session.add(cust)
        session.add(plat)
        await session.flush()
        cust_id = cust.id
        plat_id = plat.id
    return cust_id, plat_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_zero_mapping_non_platform_tenant_is_denied(client):  # noqa: ARG001
    """is_platform_scope=False + zero mappings → all access methods deny."""
    cust_id, _ = asyncio.run(_seed_tenants())

    zone = CloudflareZone(id="z1", name="example.com", status="active")

    async def _run() -> tuple[bool, tuple]:
        async with session_scope() as session:
            flt = TenantResourceFilter(session, cust_id)

            accessible = await flt.is_resource_accessible(
                provider=PROVIDER_CLOUDFLARE,
                resource_type=RESOURCE_TYPE_DNS_ZONE,
                external_id="z1",
            )

            zones_out, records_out, selected_out = await flt.filter_dns(
                [zone], [], selected_zone=zone.id
            )

        return accessible, (zones_out, records_out, selected_out)

    accessible, (zones_out, records_out, selected_out) = asyncio.run(_run())

    assert accessible is False, "is_resource_accessible should deny a non-platform tenant with no mappings"
    assert zones_out == [], "filter_dns should return empty zones for non-platform tenant with no mappings"
    assert records_out == [], "filter_dns should return empty records for non-platform tenant with no mappings"
    assert selected_out == "", "filter_dns should return empty selected_zone for non-platform tenant with no mappings"


def test_platform_scope_tenant_sees_all_without_mappings(client):  # noqa: ARG001
    """is_platform_scope=True + zero mappings → fall-open (all resources visible)."""
    _, plat_id = asyncio.run(_seed_tenants())

    zone = CloudflareZone(id="z1", name="example.com", status="active")

    async def _run() -> tuple[bool, tuple]:
        async with session_scope() as session:
            flt = TenantResourceFilter(session, plat_id)

            accessible = await flt.is_resource_accessible(
                provider=PROVIDER_CLOUDFLARE,
                resource_type=RESOURCE_TYPE_DNS_ZONE,
                external_id="z1",
            )

            zones_out, records_out, selected_out = await flt.filter_dns(
                [zone], [], selected_zone=zone.id
            )

        return accessible, (zones_out, records_out, selected_out)

    accessible, (zones_out, records_out, selected_out) = asyncio.run(_run())

    assert accessible is True, "is_resource_accessible should allow a platform-scope tenant with no mappings"
    assert zones_out == [zone], "filter_dns should return all zones for platform-scope tenant"
    assert selected_out == zone.id, "filter_dns should preserve selected_zone for platform-scope tenant"
