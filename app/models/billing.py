"""Reseller billing — pricing rules + the append-only charge ledger (slice 1).

Provider-agnostic: an offering (keyed `cf.plan_pro`, `ai.usage`, `hetzner.cx32`, …) has a
wholesale cost (what Tetra pays) and a pricing rule (cost → markup → resale). Every billable
event lands in the `ResellerCharge` ledger — the source of truth for invoicing + margin.
Slice 1 moves no real money; it computes prices and records charges.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, String
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
