"""Domains — custom hostnames for native (Tetra Engine) apps, verified via DNS TXT.

A tenant claims a hostname for one of their apps; ownership is proven by publishing a
TXT record ``_tetra-challenge.<hostname>`` containing the issued token. Only verified
domains are routed at the edge and answered by the Caddy on-demand-TLS ``ask`` endpoint.
TXT lookups run through an **injectable async resolver** (default shells out to ``dig``,
mirroring the builder/docker_engine runner pattern) so verification is unit-testable
without network access.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from secrets import token_hex

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Domain, TenantResource
from app.models.domain import DOMAIN_PENDING, DOMAIN_VERIFIED
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services.docker_engine import DockerEngineError
from app.services.edge import app_hostname

# hostname -> TXT record strings
TxtResolver = Callable[[str], Awaitable[list[str]]]

_HOSTNAME = re.compile(
    r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
CHALLENGE_PREFIX = "_tetra-challenge"


async def _dig_txt_resolver(name: str) -> list[str]:
    """Default resolver: ``dig +short TXT <name>`` (ubiquitous on the hosts we target)."""
    proc = await asyncio.create_subprocess_exec(
        "dig", "+short", "TXT", name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, _ = await proc.communicate()
    lines = out_b.decode("utf-8", "replace").splitlines()
    return [line.strip().strip('"') for line in lines if line.strip()]


class DomainsService:
    def __init__(self, resolver: TxtResolver | None = None) -> None:
        self._resolve = resolver or _dig_txt_resolver

    @staticmethod
    def normalize_hostname(hostname: str) -> str:
        host = (hostname or "").strip().lower().rstrip(".")
        if not _HOSTNAME.match(host):
            raise ValueError("Enter a valid domain name, e.g. www.example.com.")
        base = get_settings().apps_base_domain
        if base and (host == base or host.endswith(f".{base}")):
            raise ValueError(f"*.{base} subdomains are assigned automatically.")
        return host

    async def _ensure_app_owned(
        self, session: AsyncSession, tenant_id: str | None, project: str
    ) -> None:
        owned = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == (tenant_id or ""),
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == project,
            )
        )
        if owned is None:
            raise DockerEngineError(message="App is not assigned to this tenant.", code=403)

    async def add_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, project: str, hostname: str
    ) -> Domain:
        host = self.normalize_hostname(hostname)
        await self._ensure_app_owned(session, tenant_id, project)
        existing = await session.scalar(select(Domain).where(Domain.hostname == host))
        if existing is not None:
            raise DockerEngineError(message="This domain is already claimed.", code=409)
        domain = Domain(
            tenant_id=tenant_id or "", project=project, hostname=host,
            status=DOMAIN_PENDING, token=token_hex(16),
        )
        session.add(domain)
        await session.flush()
        return domain

    async def list_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str | None = None
    ) -> list[Domain]:
        query = select(Domain).where(Domain.tenant_id == (tenant_id or ""))
        if project:
            query = query.where(Domain.project == project)
        rows = await session.scalars(query.order_by(Domain.created_at.desc()))
        return list(rows.all())

    async def get_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, domain_id: str
    ) -> Domain | None:
        domain = await session.get(Domain, domain_id)
        if domain is not None and domain.tenant_id == (tenant_id or ""):
            return domain
        return None

    async def verify_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, domain_id: str
    ) -> Domain:
        domain = await self.get_for_tenant(session, tenant_id, domain_id)
        if domain is None:
            raise DockerEngineError(message="Domain not found.", code=404)
        if domain.status == DOMAIN_VERIFIED:
            return domain
        records = await self._resolve(f"{CHALLENGE_PREFIX}.{domain.hostname}")
        if domain.token not in records:
            raise DockerEngineError(
                message=(
                    f"TXT record not found. Add: {CHALLENGE_PREFIX}.{domain.hostname} "
                    f"TXT \"{domain.token}\" and retry (DNS may take a few minutes)."
                ),
                code=409,
            )
        domain.status = DOMAIN_VERIFIED
        return domain

    async def delete_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, domain_id: str
    ) -> bool:
        domain = await self.get_for_tenant(session, tenant_id, domain_id)
        if domain is None:
            return False
        await session.delete(domain)
        return True

    async def is_hostname_verified(self, session: AsyncSession, hostname: str) -> bool:
        """Edge ``ask`` check — NOT tenant-scoped (Caddy is the caller, not a session)."""
        host = (hostname or "").strip().lower().rstrip(".")
        if not host:
            return False
        domain = await session.scalar(
            select(Domain).where(Domain.hostname == host, Domain.status == DOMAIN_VERIFIED)
        )
        return domain is not None

    async def verified_hostnames_for_project(
        self, session: AsyncSession, tenant_id: str | None, project: str
    ) -> list[str]:
        rows = await session.scalars(
            select(Domain.hostname).where(
                Domain.tenant_id == (tenant_id or ""),
                Domain.project == project,
                Domain.status == DOMAIN_VERIFIED,
            )
        )
        return list(rows.all())

    @staticmethod
    def instructions(domain: Domain) -> dict[str, str]:
        """What the tenant must publish: the TXT challenge + a CNAME to the app host."""
        return {
            "txt_name": f"{CHALLENGE_PREFIX}.{domain.hostname}",
            "txt_value": domain.token,
            "cname_target": app_hostname(domain.project),
        }
