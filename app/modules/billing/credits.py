"""Prepaid credit wallet — per-tenant balance in micro-USD with an append-only transaction
log. Powers metered AI-gateway billing: top-ups add credit, each metered call debits it, and
the balance gates whether a tenant may start a new call (soft cap: check-before, settle-after).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.billing import (
    MICRO_USD_PER_USD,
    TXN_ADJUSTMENT,
    TXN_DEBIT,
    TXN_TOPUP,
    AiUsageEvent,
    CreditTransaction,
    TenantCredit,
)


class CreditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _wallet(self, tenant_id: str, *, create: bool = False) -> TenantCredit | None:
        wallet = await self.session.get(TenantCredit, tenant_id)
        if wallet is None and create:
            wallet = TenantCredit(tenant_id=tenant_id, balance_micro_usd=0)
            self.session.add(wallet)
            await self.session.flush()
        return wallet

    async def balance(self, tenant_id: str) -> int:
        """Current balance in micro-USD (0 when the tenant has no wallet yet)."""
        wallet = await self._wallet(tenant_id)
        return wallet.balance_micro_usd if wallet else 0

    async def _apply(self, tenant_id: str, delta: int, *, kind: str, reference: str) -> int:
        wallet = await self._wallet(tenant_id, create=True)
        assert wallet is not None
        wallet.balance_micro_usd += delta
        self.session.add(
            CreditTransaction(
                tenant_id=tenant_id, delta_micro_usd=delta, kind=kind, reference=reference
            )
        )
        await self.session.flush()
        return wallet.balance_micro_usd

    async def topup(self, tenant_id: str, amount_micro_usd: int, *, reference: str = "") -> int:
        """Add prepaid credit (amount must be positive). Returns the new balance."""
        if amount_micro_usd <= 0:
            raise ValueError("Top-up amount must be positive.")
        return await self._apply(tenant_id, amount_micro_usd, kind=TXN_TOPUP, reference=reference)

    async def debit(self, tenant_id: str, amount_micro_usd: int, *, reference: str = "") -> int:
        """Consume credit for metered usage. Settle-after means the balance may dip slightly
        negative on the final call; that's expected and reconciled by the next top-up."""
        if amount_micro_usd < 0:
            raise ValueError("Debit amount must be non-negative.")
        return await self._apply(tenant_id, -amount_micro_usd, kind=TXN_DEBIT, reference=reference)

    async def adjust(self, tenant_id: str, delta_micro_usd: int, *, reference: str = "") -> int:
        """Manual compensating correction (can be positive or negative)."""
        return await self._apply(tenant_id, delta_micro_usd, kind=TXN_ADJUSTMENT, reference=reference)

    async def overview(self, *, days: int = 30) -> list[dict]:
        """Platform-admin view: every tenant with its wallet balance + recent AI spend."""
        tenants = list((await self.session.scalars(select(Tenant))).all())
        wallets = {
            w.tenant_id: w.balance_micro_usd
            for w in (await self.session.scalars(select(TenantCredit))).all()
        }
        since = datetime.now(UTC) - timedelta(days=days)
        rows = (
            await self.session.execute(
                select(
                    AiUsageEvent.tenant_id,
                    func.sum(AiUsageEvent.billed_micro_usd),
                    func.count(),
                )
                .where(AiUsageEvent.created_at >= since)
                .group_by(AiUsageEvent.tenant_id)
            )
        ).all()
        spend = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in rows}
        out: list[dict] = []
        for t in tenants:
            billed, count = spend.get(t.id, (0, 0))
            out.append({
                "tenant_id": t.id,
                "tenant_name": t.name,
                "balance_usd": wallets.get(t.id, 0) / MICRO_USD_PER_USD,
                "spend_30d_usd": billed / MICRO_USD_PER_USD,
                "requests_30d": count,
            })
        out.sort(key=lambda x: x["spend_30d_usd"], reverse=True)
        return out

    async def transactions(self, tenant_id: str, *, limit: int = 100) -> list[CreditTransaction]:
        rows = await self.session.scalars(
            select(CreditTransaction)
            .where(CreditTransaction.tenant_id == tenant_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
        )
        return list(rows.all())
