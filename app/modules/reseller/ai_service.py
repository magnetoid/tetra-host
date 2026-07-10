"""AI reselling — provision per-tenant OpenRouter runtime keys (Path A: direct keys).

A tenant activates AI access → we mint an OpenRouter runtime key with a spend cap sized to
their plan; the secret is surfaced **once** and never stored (only the non-secret ``hash``
is recorded as a ``TenantResource`` for management). Ownership is fail-closed (a tenant may
only manage keys it provisioned → 404 otherwise). Writes gated by ``ENABLE_PROVIDER_ACTIONS``.
"""

from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    MICRO_USD_PER_USD,
    RULE_MARKUP_PERCENT,
    AiUsageEvent,
    PricingRule,
)
from app.models.tenant_resource import (
    PROVIDER_OPENROUTER,
    RESOURCE_TYPE_AI_KEY,
    TenantResource,
)
from app.modules.billing.credits import CreditService
from app.modules.reseller.service import ResellerError
from app.services.http import ProviderAPIError
from app.services.openrouter import MODE_DISABLED, MODE_GATEWAY, OpenRouterClient
from app.services.tenant_resources import TenantResourceFilter

# The metered AI-usage offering key (billing ledger + PricingRule override live under this).
AI_USAGE_OFFERING = "ai.usage"


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

    def mode(self) -> str:
        """Which AI billing model is live: 'keys' (Model B), 'gateway' (Model A), 'disabled'."""
        return self.client.mode()

    async def platform_credits(self) -> dict:
        """The shared gateway key's own balance (gateway mode only)."""
        if self.client.mode() != MODE_GATEWAY:
            return {}
        try:
            return await self.client.get_credits()
        except ProviderAPIError:
            return {}

    async def usage_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, days: int = 30, limit: int = 100
    ) -> dict:
        """Per-tenant AI spend over a window: totals, per-model breakdown, recent events."""
        if not tenant_id:
            return {"total_billed_usd": 0.0, "total_cost_usd": 0.0, "total_requests": 0,
                    "by_model": [], "events": []}
        since = datetime.now(UTC) - timedelta(days=days)
        rows = list(
            (
                await session.scalars(
                    select(AiUsageEvent)
                    .where(AiUsageEvent.tenant_id == tenant_id, AiUsageEvent.created_at >= since)
                    .order_by(AiUsageEvent.created_at.desc())
                )
            ).all()
        )
        total_cost = sum(r.cost_micro_usd for r in rows)
        total_billed = sum(r.billed_micro_usd for r in rows)
        by_model: dict[str, dict] = {}
        for r in rows:
            m = by_model.setdefault(r.model or "unknown", {"model": r.model or "unknown", "requests": 0, "billed_micro": 0})
            m["requests"] += 1
            m["billed_micro"] += r.billed_micro_usd
        return {
            "total_billed_usd": total_billed / MICRO_USD_PER_USD,
            "total_cost_usd": total_cost / MICRO_USD_PER_USD,
            "total_requests": len(rows),
            "by_model": [
                {"model": v["model"], "requests": v["requests"], "billed_usd": v["billed_micro"] / MICRO_USD_PER_USD}
                for v in sorted(by_model.values(), key=lambda x: x["billed_micro"], reverse=True)
            ],
            "events": [
                {
                    "model": r.model, "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "cost_usd": r.cost_micro_usd / MICRO_USD_PER_USD,
                    "billed_usd": r.billed_micro_usd / MICRO_USD_PER_USD,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows[:limit]
            ],
        }

    async def _ai_markup_percent(self, session: AsyncSession) -> float:
        rule = await session.scalar(
            select(PricingRule).where(PricingRule.offering_key == AI_USAGE_OFFERING)
        )
        if rule is not None and rule.rule == RULE_MARKUP_PERCENT:
            return rule.rule_value
        return self.settings.reseller_default_markup_percent

    async def chat_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, body: dict
    ) -> dict:
        """Shared-gateway (Model A) chat proxy with per-tenant metering.

        Flow: require a prepaid balance → forward to OpenRouter on the shared key → read the
        inline ``usage.cost`` → apply markup → record an AiUsageEvent + debit the wallet. Soft
        cap: we check before and settle after, so the final call may dip the balance negative.
        """
        if not self.settings.enable_provider_actions:
            raise ResellerError("Provider actions are disabled.", status_code=403)
        mode = self.client.mode()
        if mode == MODE_DISABLED:
            raise ResellerError("AI is not configured on this platform.", status_code=503)
        if mode != MODE_GATEWAY:
            raise ResellerError(
                "This platform provisions per-tenant AI keys — call OpenRouter directly with yours.",
                status_code=400,
            )
        if not tenant_id:
            raise ResellerError("A tenant context is required.", status_code=400)
        if not isinstance(body, dict) or not body.get("model") or not body.get("messages"):
            raise ResellerError("Request must include 'model' and 'messages'.", status_code=422)

        credits = CreditService(session)
        if await credits.balance(tenant_id) <= 0:
            raise ResellerError(
                "Insufficient AI credit. Ask an admin to top up your balance.", status_code=402
            )

        result = await self.client.chat_completion(body)
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        cost_usd = float(usage.get("cost") or 0.0)
        cost_micro = max(0, round(cost_usd * MICRO_USD_PER_USD))
        markup = await self._ai_markup_percent(session)
        billed_micro = round(cost_micro * (1 + markup / 100.0))
        request_id = str(result.get("id") or "")
        model = str(body.get("model") or "")

        session.add(
            AiUsageEvent(
                tenant_id=tenant_id, model=model,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                cost_micro_usd=cost_micro, billed_micro_usd=billed_micro, request_id=request_id,
            )
        )
        await session.flush()
        balance = await credits.debit(tenant_id, billed_micro, reference=request_id or "ai.usage")

        return {
            "completion": result,
            "usage": {
                "model": model,
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "cost_usd": cost_usd,
                "billed_usd": billed_micro / MICRO_USD_PER_USD,
                "request_id": request_id,
            },
            "balance_micro_usd": balance,
            "balance_usd": balance / MICRO_USD_PER_USD,
        }

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
