"""Resolve an engine app (a Tetra Engine stack) for observability sidecars.

Every engine app — git deploy, marketplace install or import — is a ``TenantResource``
(provider ``docker``, type ``app``) keyed by its compose project name. Analytics (Umami) and
errors (GlitchTip) need the same two things from it: a tenant check and a public domain.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Deployment, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services.tenant_resources import TenantResourceFilter


class EngineAppNotFound(Exception):
    """The app does not exist or is not this tenant's (callers answer 403/404)."""


@dataclass(frozen=True)
class EngineAppRef:
    project: str
    name: str
    domain: str


async def resolve_engine_app(
    session: AsyncSession, tenant_id: str | None, project: str
) -> EngineAppRef:
    access = TenantResourceFilter(session, tenant_id)
    allowed = await access.is_resource_accessible(
        provider=PROVIDER_DOCKER, resource_type=RESOURCE_TYPE_APP, external_id=project
    )
    if not allowed:
        raise EngineAppNotFound(project)
    # Platform scope may look at any tenant's app; everyone else only at their own.
    platform = await access.is_platform()
    resource_q = select(TenantResource).where(
        TenantResource.provider == PROVIDER_DOCKER,
        TenantResource.resource_type == RESOURCE_TYPE_APP,
        TenantResource.external_id == project,
    )
    deploy_q = (
        select(Deployment.domain)
        .where(Deployment.project == project, Deployment.domain != "")
        .order_by(Deployment.created_at.desc())
        .limit(1)
    )
    if not platform:
        resource_q = resource_q.where(TenantResource.tenant_id == (tenant_id or ""))
        deploy_q = deploy_q.where(Deployment.tenant_id == (tenant_id or ""))
    resource = (await session.scalars(resource_q.limit(1))).first()
    if resource is None:
        raise EngineAppNotFound(project)
    domain = await session.scalar(deploy_q) or ""
    if not domain and get_settings().apps_base_domain:
        domain = f"{project}.{get_settings().apps_base_domain}"
    return EngineAppRef(project=project, name=resource.display_name or project, domain=domain)
