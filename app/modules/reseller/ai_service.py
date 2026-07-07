"""AI reselling — provision per-tenant OpenRouter runtime keys (Path A: direct keys).

A tenant activates AI access → we mint an OpenRouter runtime key with a spend cap sized to
their plan; the secret is surfaced **once** and never stored (only the non-secret ``hash``
is recorded as a ``TenantResource`` for management). Ownership is fail-closed (a tenant may
only manage keys it provisioned → 404 otherwise). Writes gated by ``ENABLE_PROVIDER_ACTIONS``.
"""

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_resource import (
    PROVIDER_OPENROUTER,
    RESOURCE_TYPE_AI_KEY,
    TenantResource,
)
from app.modules.reseller.service import ResellerError
from app.services.http import ProviderAPIError
from app.services.openrouter import OpenRouterClient
from app.services.tenant_resources import TenantResourceFilter


class AiResellerService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = OpenRouterClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )
        self.settings = request.state.settings

    def _require_actions(self) -> None:
        if not self.settings.enable_provider_actions:
            raise ResellerError("Provider actions are disabled.", status_code=403)

    async def list_models(self) -> list[dict]:
        """The public OpenRouter model catalog (the resellable menu)."""
        return await self.client.list_models()

    async def _owned_hashes(self, session: AsyncSession, tenant_id: str | None) -> set[str]:
        if not tenant_id:
            return set()
        rows = await session.scalars(
            select(TenantResource.external_id).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_OPENROUTER,
                TenantResource.resource_type == RESOURCE_TYPE_AI_KEY,
            )
        )
        return {r for r in rows.all() if r}

    async def _ensure_key_owned(
        self, session: AsyncSession, tenant_id: str | None, key_hash: str
    ) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_OPENROUTER, resource_type=RESOURCE_TYPE_AI_KEY, external_id=key_hash,
        )
        if not allowed:
            raise ResellerError("Key not found.", status_code=404)

    async def list_keys_for_tenant(self, session: AsyncSession, tenant_id: str | None) -> list[dict]:
        keys: list[dict] = []
        for key_hash in await self._owned_hashes(session, tenant_id):
            try:
                data = await self.client.get_key(key_hash)
            except ProviderAPIError:
                data = {"hash": key_hash}
            keys.append(data)
        return keys

    async def provision_key_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *,
        label: str, limit: float | None = None, limit_reset: str = "monthly",
    ) -> dict:
        self._require_actions()
        name = label.strip() or f"tenant-{tenant_id}"
        result = await self.client.create_key(name, limit=limit, limit_reset=limit_reset)
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        key_hash = str(data.get("hash") or "")
        secret = str(result.get("key") or "")
        if tenant_id and key_hash:
            session.add(
                TenantResource(
                    tenant_id=tenant_id, provider=PROVIDER_OPENROUTER,
                    resource_type=RESOURCE_TYPE_AI_KEY, external_id=key_hash, display_name=name,
                )
            )
            await session.flush()
        return {"key": secret, "hash": key_hash, "label": name, "limit": data.get("limit")}

    async def update_key_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, key_hash: str, *,
        limit: float | None = None, disabled: bool | None = None,
    ) -> dict:
        self._require_actions()
        await self._ensure_key_owned(session, tenant_id, key_hash)
        return await self.client.update_key(key_hash, limit=limit, disabled=disabled)

    async def revoke_key_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, key_hash: str
    ) -> None:
        self._require_actions()
        await self._ensure_key_owned(session, tenant_id, key_hash)
        await self.client.delete_key(key_hash)
        existing = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_OPENROUTER,
                TenantResource.resource_type == RESOURCE_TYPE_AI_KEY,
                TenantResource.external_id == key_hash,
            )
        )
        if existing is not None:
            await session.delete(existing)
            await session.flush()
