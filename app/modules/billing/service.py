"""Billing — reseller pricing resolution + the charge ledger (slice 1).

Pure money math + records; no payment rails yet. Resolve a resale price for any offering
(per-offering PricingRule → else the platform default markup), and append every billable
event to the ResellerCharge ledger for invoicing + margin reporting.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.billing import (
    RULE_FIXED_MARGIN,
    RULE_FIXED_PRICE,
    RULE_MARKUP_PERCENT,
    CHARGE_PENDING,
    PricingRule,
    ResellerCharge,
)


class BillingError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def compute_resale_cents(wholesale_cents: int, rule: str, rule_value: float) -> int:
    """cost → resale. markup_percent: +p%. fixed_margin: +cents. fixed_price: absolute."""
    if rule == RULE_FIXED_PRICE:
        return max(0, int(round(rule_value)))
    if rule == RULE_FIXED_MARGIN:
        return max(0, wholesale_cents + int(round(rule_value)))
    # default: markup_percent
    return max(0, int(round(wholesale_cents * (1 + rule_value / 100.0))))


class BillingService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def get_rule(self, offering_key: str) -> PricingRule | None:
        return await self.session.scalar(
            select(PricingRule).where(PricingRule.offering_key == offering_key)
        )

    async def list_rules(self) -> list[PricingRule]:
        rows = await self.session.scalars(select(PricingRule).order_by(PricingRule.offering_key))
        return list(rows.all())

    async def quote(self, offering_key: str, *, wholesale_cents: int | None = None) -> dict:
        """Resolve the resale price. Uses the offering's PricingRule if present; otherwise
        applies the platform default markup to `wholesale_cents` (required in that case)."""
        rule = await self.get_rule(offering_key)
        if rule is not None:
            wholesale = wholesale_cents if wholesale_cents is not None else rule.wholesale_cost_cents
            rule_name, rule_value = rule.rule, rule.rule_value
        else:
            if wholesale_cents is None:
                raise BillingError(
                    f"No pricing configured for '{offering_key}' — set a rule or pass a wholesale cost.",
                    status_code=404,
                )
            wholesale = wholesale_cents
            rule_name = RULE_MARKUP_PERCENT
            rule_value = self.settings.reseller_default_markup_percent

        resale = compute_resale_cents(wholesale, rule_name, rule_value)
        return {
            "offering_key": offering_key,
            "wholesale_cost_cents": wholesale,
            "resale_price_cents": resale,
            "margin_cents": resale - wholesale,
            "rule": rule_name,
            "rule_value": rule_value,
        }

    async def set_rule(
        self, offering_key: str, *, provider: str, cost_shape: str,
        wholesale_cost_cents: int, unit: str, rule: str, rule_value: float,
    ) -> PricingRule:
        existing = await self.get_rule(offering_key)
        if existing is None:
            existing = PricingRule(offering_key=offering_key)
            self.session.add(existing)
        existing.provider = provider
        existing.cost_shape = cost_shape
        existing.wholesale_cost_cents = wholesale_cost_cents
        existing.unit = unit
        existing.rule = rule
        existing.rule_value = rule_value
        await self.session.flush()
        return existing

    async def record_charge(
        self, *, tenant_id: str, offering_key: str, provider: str,
        wholesale_cost_cents: int, resale_price_cents: int, status: str = CHARGE_PENDING,
    ) -> ResellerCharge:
        charge = ResellerCharge(
            tenant_id=tenant_id, offering_key=offering_key, provider=provider,
            wholesale_cost_cents=wholesale_cost_cents, resale_price_cents=resale_price_cents,
            margin_cents=resale_price_cents - wholesale_cost_cents, status=status,
        )
        self.session.add(charge)
        await self.session.flush()
        return charge

    async def list_charges(self, *, tenant_id: str | None = None, limit: int = 100) -> list[ResellerCharge]:
        query = select(ResellerCharge).order_by(ResellerCharge.created_at.desc()).limit(limit)
        if tenant_id is not None:
            query = query.where(ResellerCharge.tenant_id == tenant_id)
        rows = await self.session.scalars(query)
        return list(rows.all())
