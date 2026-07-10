"""Reseller billing — pricing rules + the append-only charge ledger (slice 1).

Provider-agnostic: an offering (keyed `cf.plan_pro`, `ai.usage`, `hetzner.cx32`, …) has a
wholesale cost (what Tetra pays) and a pricing rule (cost → markup → resale). Every billable
event lands in the `ResellerCharge` ledger — the source of truth for invoicing + margin.
Slice 1 moves no real money; it computes prices and records charges.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


COST_SHAPE_RECURRING = "recurring"
COST_SHAPE_METERED = "metered"

RULE_MARKUP_PERCENT = "markup_percent"  # rule_value = percent, e.g. 30.0
RULE_FIXED_MARGIN = "fixed_margin"  # rule_value = added cents
RULE_FIXED_PRICE = "fixed_price"  # rule_value = absolute cents

CHARGE_PENDING = "pending"
CHARGE_INVOICED = "invoiced"
CHARGE_PAID = "paid"

# Fine-grained money for metered AI usage: 1 USD = 1,000,000 micro-USD. Summing millions of
# sub-cent per-request costs in integer micro-USD avoids float drift; render to cents only at
# the presentation edge. The prepaid credit wallet is kept in the same unit.
MICRO_USD_PER_USD = 1_000_000
MICRO_USD_PER_CENT = 10_000

TXN_TOPUP = "topup"  # admin/prepaid credit added
TXN_DEBIT = "debit"  # metered usage consumed
TXN_ADJUSTMENT = "adjustment"  # manual correction (compensating entry)


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    offering_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    cost_shape: Mapped[str] = mapped_column(String(20), default=COST_SHAPE_RECURRING, nullable=False)
    wholesale_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(60), default="", nullable=False)  # metered unit label
    rule: Mapped[str] = mapped_column(String(30), default=RULE_MARKUP_PERCENT, nullable=False)
    rule_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ResellerCharge(Base):
    __tablename__ = "reseller_charges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    offering_key: Mapped[str] = mapped_column(String(120), index=True)
    provider: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    wholesale_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resale_price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    margin_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=CHARGE_PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TenantCredit(Base):
    """Prepaid credit wallet balance per tenant, in micro-USD (see MICRO_USD_PER_USD).
    Authoritative running balance; every change is also appended to CreditTransaction."""

    __tablename__ = "tenant_credits"

    tenant_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    balance_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class CreditTransaction(Base):
    """Append-only wallet ledger — top-ups (+), metered debits (−), and adjustments.
    Immutable: corrections are new compensating rows, never edits."""

    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    delta_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default=TXN_TOPUP, nullable=False)
    reference: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AiUsageEvent(Base):
    """One row per metered AI gateway call — the source of truth for per-tenant AI spend,
    breakdowns (by model), and margin. Wholesale = OpenRouter's inline usage.cost; billed =
    after markup. Both in micro-USD."""

    __tablename__ = "ai_usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    billed_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    request_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
