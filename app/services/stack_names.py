"""Engine stack names are global on the host.

A compose project name (and the hostname derived from it) is shared by every tenant on the box,
so a new workload must not reuse a name any tenant already runs: git deploys and template
installs (``TenantResource`` docker/app), managed databases and preview stacks.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ManagedDatabase, PreviewEnv, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP


async def stack_owner(session: AsyncSession, project: str) -> str | None:
    """The tenant id that already runs stack ``project`` (``""`` for platform scope), or
    ``None`` when the name is free."""
    owner = await session.scalar(
        select(TenantResource.tenant_id).where(
            TenantResource.provider == PROVIDER_DOCKER,
            TenantResource.resource_type == RESOURCE_TYPE_APP,
            TenantResource.external_id == project,
        ).limit(1)
    )
    if owner is not None:
        return str(owner)
    for column, tenant_column in (
        (ManagedDatabase.project, ManagedDatabase.tenant_id),
        (PreviewEnv.preview_project, PreviewEnv.tenant_id),
    ):
        owner = await session.scalar(select(tenant_column).where(column == project).limit(1))
        if owner is not None:
            return str(owner)
    return None
