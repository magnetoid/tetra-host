"""Reseller — resell Cloudflare plans + services on tenant zones (Path A).

Everything runs on the platform Cloudflare token; resold plans/services are scoped to
tenants via ``TenantResource`` (exactly like DNS). Ownership is fail-closed: the target
zone must be a tenant-accessible ``dns_zone`` or the call 404s (never leak which zones
exist). All writes are gated behind ``ENABLE_PROVIDER_ACTIONS``. The Cloudflare Tenant
API (real customer sub-accounts) is Path B — added when partner onboarding lands.
"""

from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    RESOURCE_TYPE_CLOUDFLARE_SERVICE,
    RESOURCE_TYPE_DNS_ZONE,
    TenantResource,
)
from app.services.cloudflare import CloudflareClient
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter


@dataclass(frozen=True)
class ResellableService:
    key: str
    name: str
    category: str  # plan | security | performance | developer
    activation: str  # plan | toggle | addon
    rate_plan: str = ""  # for activation == "plan"
    description: str = ""


# The resellable Cloudflare catalog. `plan`/security services activate by (up)grading the
# zone's rate plan; `toggle` services flip a zone endpoint; `addon` services are account-
# level (Workers/R2/LB) — recorded as pending until account provisioning is wired.
CLOUDFLARE_SERVICES: list[ResellableService] = [
    ResellableService("plan_pro", "Pro Plan", "plan", "plan", rate_plan="pro",
                      description="WAF, image optimization, and enhanced performance."),
    ResellableService("plan_business", "Business Plan", "plan", "plan", rate_plan="business",
                      description="Advanced WAF, 100% uptime SLA, custom SSL."),
    ResellableService("plan_enterprise", "Enterprise Plan", "plan", "plan", rate_plan="enterprise",
                      description="Enterprise support and advanced controls."),
    ResellableService("waf_managed", "WAF Managed Rules", "security", "plan", rate_plan="pro",
                      description="Cloudflare-managed WAF rulesets (Pro plan or above)."),
    ResellableService("rate_limiting", "Advanced Rate Limiting", "security", "plan", rate_plan="business",
                      description="Granular rate limiting (Business plan or above)."),
    ResellableService("argo", "Argo Smart Routing", "performance", "toggle",
                      description="Route traffic over Cloudflare's fastest paths."),
    ResellableService("load_balancing", "Load Balancing", "performance", "addon",
                      description="Traffic steering + health-checked failover (add-on subscription)."),
    ResellableService("workers", "Workers", "developer", "addon",
                      description="Serverless functions at the edge (account add-on)."),
    ResellableService("r2", "R2 Storage", "developer", "addon",
                      description="S3-compatible object storage (account add-on)."),
]

_SERVICE_BY_KEY = {s.key: s for s in CLOUDFLARE_SERVICES}


class ResellerError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ResellerService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CloudflareClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )
        self.settings = request.state.settings

    def catalog(self) -> list[ResellableService]:
        return CLOUDFLARE_SERVICES

    async def _ensure_zone_access(
        self, session: AsyncSession, tenant_id: str | None, zone_id: str
    ) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_CLOUDFLARE, resource_type=RESOURCE_TYPE_DNS_ZONE, external_id=zone_id,
        )
        if not allowed:
            raise ResellerError("Zone not found.", status_code=404)

    def _require_actions(self) -> None:
        if not self.settings.enable_provider_actions:
            raise ResellerError("Provider actions are disabled.", status_code=403)

    async def list_plans_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, zone_id: str
    ) -> list[dict]:
        await self._ensure_zone_access(session, tenant_id, zone_id)
        return await self.client.list_available_plans(zone_id)

    async def get_subscription_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, zone_id: str
    ) -> dict:
        await self._ensure_zone_access(session, tenant_id, zone_id)
        try:
            return await self.client.get_zone_subscription(zone_id)
        except ProviderAPIError:
            return {}  # no subscription yet — treated as "on free"

    async def activate_plan_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, zone_id: str,
        rate_plan_id: str, *, frequency: str = "monthly",
    ) -> dict:
        self._require_actions()
        await self._ensure_zone_access(session, tenant_id, zone_id)
        existing = await self.get_subscription_for_tenant(session, tenant_id, zone_id)
        result = await self.client.set_zone_subscription(
            zone_id, rate_plan_id, frequency=frequency, update=bool(existing.get("id")),
        )
        await self._record(session, tenant_id, zone_id, f"plan:{rate_plan_id}")
        return result

    async def activate_service_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, zone_id: str, service_key: str
    ) -> dict:
        self._require_actions()
        await self._ensure_zone_access(session, tenant_id, zone_id)
        service = _SERVICE_BY_KEY.get(service_key)
        if service is None:
            raise ResellerError(f"Unknown service '{service_key}'.", status_code=404)

        result: dict = {}
        if service.activation == "plan":
            existing = await self.get_subscription_for_tenant(session, tenant_id, zone_id)
            result = await self.client.set_zone_subscription(
                zone_id, service.rate_plan, update=bool(existing.get("id")),
            )
            note = f"{service.name} activated via the {service.rate_plan} plan."
        elif service.activation == "toggle" and service.key == "argo":
            result = await self.client.set_argo_smart_routing(zone_id, True)
            note = "Argo Smart Routing enabled."
        else:  # account-level add-on — not yet auto-provisioned
            note = f"{service.name} requested — account-level provisioning, recorded as pending."

        await self._record(session, tenant_id, zone_id, f"service:{service_key}")
        return {"service": service_key, "note": note, "result": result}

    async def _record(
        self, session: AsyncSession, tenant_id: str | None, zone_id: str, display: str
    ) -> None:
        """Register the activation as a TenantResource (idempotent per zone+service)."""
        if not tenant_id:
            return
        external_id = f"{zone_id}:{display}"
        existing = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_CLOUDFLARE,
                TenantResource.resource_type == RESOURCE_TYPE_CLOUDFLARE_SERVICE,
                TenantResource.external_id == external_id,
            )
        )
        if existing is None:
            session.add(
                TenantResource(
                    tenant_id=tenant_id, provider=PROVIDER_CLOUDFLARE,
                    resource_type=RESOURCE_TYPE_CLOUDFLARE_SERVICE,
                    external_id=external_id, display_name=display,
                )
            )
            await session.flush()
