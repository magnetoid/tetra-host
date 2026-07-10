"""Object storage reselling — per-tenant Cloudflare R2 buckets (Path A).

A tenant provisions a bucket → we create it under the platform R2 account, namespaced by
tenant to avoid the account-global name collisions, record a ``TenantResource`` (fail-closed
ownership), and — when credential issuance is configured — mint bucket-scoped S3 credentials
returned ONCE. Writes gated by ``ENABLE_PROVIDER_ACTIONS``.
"""

import re

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    RESOURCE_TYPE_BUCKET,
    TenantResource,
)
from app.modules.reseller.service import ResellerError
from app.services.r2 import R2Client
from app.services.tenant_resources import TenantResourceFilter


def _sanitize_bucket_name(tenant_id: str, name: str) -> str:
    """R2 bucket names are account-global, lowercase, 3–63 chars. Namespace by tenant."""
    prefix = re.sub(r"[^a-z0-9]+", "", (tenant_id or "t").lower())[:8] or "t"
    slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")[:40] or "bucket"
    return f"{prefix}-{slug}"[:63]


class StorageService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = R2Client.from_settings(
            http_client=request.app.state.http_client, cache=request.app.state.cache
        )
        self.settings = request.state.settings

    def _require_actions(self) -> None:
        if not self.settings.enable_provider_actions:
            raise ResellerError("Provider actions are disabled.", status_code=403)

    def is_configured(self) -> bool:
        return self.client.is_configured()

    async def _owned_names(self, session: AsyncSession, tenant_id: str | None) -> set[str]:
        if not tenant_id:
            return set()
        rows = await session.scalars(
            select(TenantResource.external_id).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_CLOUDFLARE,
                TenantResource.resource_type == RESOURCE_TYPE_BUCKET,
            )
        )
        return {r for r in rows.all() if r}

    async def _ensure_owned(self, session: AsyncSession, tenant_id: str | None, name: str) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_CLOUDFLARE, resource_type=RESOURCE_TYPE_BUCKET, external_id=name
        )
        if not allowed:
            raise ResellerError("Bucket not found.", status_code=404)

    async def list_buckets_for_tenant(self, session: AsyncSession, tenant_id: str | None) -> list[dict]:
        rows = list(
            (
                await session.scalars(
                    select(TenantResource).where(
                        TenantResource.tenant_id == (tenant_id or ""),
                        TenantResource.provider == PROVIDER_CLOUDFLARE,
                        TenantResource.resource_type == RESOURCE_TYPE_BUCKET,
                    )
                )
            ).all()
        )
        endpoint = self.client.s3_endpoint if self.client.is_configured() else ""
        return [
            {"name": r.external_id, "display_name": r.display_name or r.external_id, "endpoint": endpoint}
            for r in rows
        ]

    async def provision_bucket_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, name: str
    ) -> dict:
        self._require_actions()
        if not self.client.is_configured():
            raise ResellerError("Object storage (R2) is not configured on this platform.", status_code=503)
        if not tenant_id:
            raise ResellerError("A tenant context is required.", status_code=400)
        bucket = _sanitize_bucket_name(tenant_id, name)

        existing = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_CLOUDFLARE,
                TenantResource.resource_type == RESOURCE_TYPE_BUCKET,
                TenantResource.external_id == bucket,
            )
        )
        if existing is not None:
            raise ResellerError(f"Bucket '{bucket}' already exists.", status_code=409)

        await self.client.create_bucket(bucket)
        session.add(
            TenantResource(
                tenant_id=tenant_id, provider=PROVIDER_CLOUDFLARE,
                resource_type=RESOURCE_TYPE_BUCKET, external_id=bucket, display_name=name.strip(),
            )
        )
        await session.flush()

        creds: dict[str, str] = {}
        if self.client.can_issue_credentials():
            creds = await self.client.create_bucket_credentials(bucket, label=f"tetra-{bucket}")
        return {
            "name": bucket,
            "endpoint": self.client.s3_endpoint,
            "access_key_id": creds.get("access_key_id", ""),
            "secret_access_key": creds.get("secret_access_key", ""),
            "credentials_issued": bool(creds.get("secret_access_key")),
        }

    async def delete_bucket_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, name: str
    ) -> None:
        self._require_actions()
        await self._ensure_owned(session, tenant_id, name)
        await self.client.delete_bucket(name)
        existing = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_CLOUDFLARE,
                TenantResource.resource_type == RESOURCE_TYPE_BUCKET,
                TenantResource.external_id == name,
            )
        )
        if existing is not None:
            await session.delete(existing)
            await session.flush()
