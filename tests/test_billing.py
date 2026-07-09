"""Reseller billing — pricing resolution + charge ledger (slice 1)."""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.modules.auth.service import AuthService
from app.modules.billing.service import compute_resale_cents


# ── Pure markup math ────────────────────────────────────────────────────────
def test_compute_resale_markup_percent():
    assert compute_resale_cents(2000, "markup_percent", 30.0) == 2600  # +30%


def test_compute_resale_fixed_margin_and_price():
    assert compute_resale_cents(2000, "fixed_margin", 500) == 2500  # +$5
    assert compute_resale_cents(2000, "fixed_price", 4999) == 4999  # absolute
    assert compute_resale_cents(0, "markup_percent", 30.0) == 0


# ── API ─────────────────────────────────────────────────────────────────────
async def _seed(*, slug: str, email: str, role: str) -> None:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(AdminUser(
            tenant_id=tenant.id, email=email, full_name="A", role=role,
            password_hash=auth.hash_password("bill-pass"), is_active=True,
        ))


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "bill-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_pricing_is_platform_admin_only(client):
    asyncio.run(_seed(slug="bo", email="o@bo.test", role=ROLE_OWNER))
    headers = _login(client, "o@bo.test")
    assert client.get("/api/v1/billing/pricing", headers=headers).status_code == 403
    assert client.put(
        "/api/v1/billing/pricing/cf.plan_pro", headers=headers,
        json={"wholesale_cost_cents": 2000},
    ).status_code == 403


def test_set_rule_then_quote_uses_it(client):
    asyncio.run(_seed(slug="bp", email="p@bp.test", role=ROLE_PLATFORM_ADMIN))
    headers = _login(client, "p@bp.test")

    put = client.put(
        "/api/v1/billing/pricing/cf.plan_pro", headers=headers,
        json={"provider": "cloudflare", "cost_shape": "recurring",
              "wholesale_cost_cents": 2000, "rule": "markup_percent", "rule_value": 30.0},
    )
    assert put.status_code == 200, put.text
    assert put.json()["resale_price_cents"] == 2600

    # quote resolves via the stored rule (no wholesale override needed)
    q = client.get("/api/v1/billing/quote/cf.plan_pro", headers=headers).json()
    assert q["resale_price_cents"] == 2600 and q["margin_cents"] == 600

    # listed
    rules = client.get("/api/v1/billing/pricing", headers=headers).json()
    assert any(r["offering_key"] == "cf.plan_pro" for r in rules)


def test_quote_falls_back_to_default_markup(client):
    asyncio.run(_seed(slug="bq", email="q@bq.test", role=ROLE_PLATFORM_ADMIN))
    headers = _login(client, "q@bq.test")
    # no rule for this offering → default 30% applied to the provided wholesale
    q = client.get("/api/v1/billing/quote/ai.usage?wholesale_cents=1000", headers=headers).json()
    assert q["rule"] == "markup_percent" and q["rule_value"] == 30.0
    assert q["resale_price_cents"] == 1300
    # no rule and no wholesale → 404
    assert client.get("/api/v1/billing/quote/ai.usage", headers=headers).status_code == 404


def test_charges_ledger_scoping(client):
    asyncio.run(_seed(slug="br", email="r@br.test", role=ROLE_PLATFORM_ADMIN))
    headers = _login(client, "r@br.test")
    # empty ledger, platform-admin path returns a list
    assert client.get("/api/v1/billing/charges", headers=headers).json() == []
