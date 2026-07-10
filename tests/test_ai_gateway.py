import asyncio

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.admin import ROLE_PLATFORM_ADMIN
from app.models.billing import MICRO_USD_PER_USD
from app.modules.auth.service import AuthService
from app.modules.billing.credits import CreditService


async def _seed(*, credit_usd: float = 0.0) -> str:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key="ai_plan", name="AI Plan", max_apps=5, max_domains=0,
                    cpu_millicores=500, mem_mb=512, disk_mb=2048)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name="AI Tenant", slug="ait", status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(AdminUser(
            tenant_id=tenant.id, email="owner@ai.test", full_name="AI Owner",
            password_hash=auth.hash_password("ai-password"), is_active=True,
        ))
        # A platform admin for the top-up (platform-admin-gated) endpoint.
        session.add(AdminUser(
            tenant_id=tenant.id, email="root@ai.test", full_name="Root",
            password_hash=auth.hash_password("root-password"), is_active=True,
            role=ROLE_PLATFORM_ADMIN,
        ))
        if credit_usd:
            await CreditService(session).topup(
                tenant.id, round(credit_usd * MICRO_USD_PER_USD), reference="seed"
            )
        return tenant.id


def _login(client, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _gateway_mode(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "openrouter_provisioning_key", "")
    monkeypatch.setattr(get_settings(), "openrouter_runtime_key", "sk-or-test-runtime")
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    async def fake_credits(self):
        return {"total_credits": 20.0, "total_usage": 5.0}

    monkeypatch.setattr("app.services.openrouter.OpenRouterClient.get_credits", fake_credits)


FAKE_COMPLETION = {
    "id": "gen-abc",
    "choices": [{"message": {"role": "assistant", "content": "Hi there!"}}],
    "usage": {"cost": 0.002, "prompt_tokens": 10, "completion_tokens": 5},
}


def test_status_reports_gateway_mode(client, monkeypatch):
    asyncio.run(_seed())
    _gateway_mode(monkeypatch)
    headers = _login(client, "owner@ai.test", "ai-password")
    r = client.get("/api/v1/ai/status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "gateway"
    assert body["configured"] is True
    assert body["platform_credit_usd"] == 15.0  # 20 - 5


def test_chat_blocked_without_credit(client, monkeypatch):
    asyncio.run(_seed(credit_usd=0.0))
    _gateway_mode(monkeypatch)

    async def fake_chat(self, body):
        raise AssertionError("must not reach OpenRouter without credit")

    monkeypatch.setattr("app.services.openrouter.OpenRouterClient.chat_completion", fake_chat)
    headers = _login(client, "owner@ai.test", "ai-password")
    r = client.post("/api/v1/ai/chat", headers=headers,
                    json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 402


def test_chat_meters_and_debits_wallet(client, monkeypatch):
    asyncio.run(_seed(credit_usd=5.0))
    _gateway_mode(monkeypatch)

    async def fake_chat(self, body):
        return FAKE_COMPLETION

    monkeypatch.setattr("app.services.openrouter.OpenRouterClient.chat_completion", fake_chat)
    headers = _login(client, "owner@ai.test", "ai-password")

    r = client.post("/api/v1/ai/chat", headers=headers,
                    json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["usage"]["cost_usd"] == 0.002
    # 0.002 * (1 + 30%) = 0.0026 billed
    assert round(body["usage"]["billed_usd"], 5) == 0.0026
    assert round(body["balance_usd"], 4) == round(5.0 - 0.0026, 4)

    usage = client.get("/api/v1/ai/usage", headers=headers).json()
    assert usage["total_requests"] == 1
    assert round(usage["total_billed_usd"], 5) == 0.0026
    assert usage["by_model"][0]["model"] == "openai/gpt-4o-mini"


def test_topup_is_platform_admin_only(client, monkeypatch):
    tenant_id = asyncio.run(_seed())
    _gateway_mode(monkeypatch)

    owner = _login(client, "owner@ai.test", "ai-password")
    denied = client.post("/api/v1/billing/credits", headers=owner,
                         json={"tenant_id": tenant_id, "amount_usd": 10})
    assert denied.status_code == 403

    root = _login(client, "root@ai.test", "root-password")
    ok = client.post("/api/v1/billing/credits", headers=root,
                     json={"tenant_id": tenant_id, "amount_usd": 10})
    assert ok.status_code == 200
    assert round(ok.json()["balance_usd"], 2) == 10.0

    # And the owner can now see their balance.
    bal = client.get("/api/v1/billing/credits", headers=owner).json()
    assert round(bal["balance_usd"], 2) == 10.0


def test_credits_overview_is_platform_admin_only(client, monkeypatch):
    tenant_id = asyncio.run(_seed(credit_usd=3.0))

    owner = _login(client, "owner@ai.test", "ai-password")
    assert client.get("/api/v1/billing/credits/overview", headers=owner).status_code == 403

    root = _login(client, "root@ai.test", "root-password")
    r = client.get("/api/v1/billing/credits/overview", headers=root)
    assert r.status_code == 200
    rows = r.json()
    match = next((x for x in rows if x["tenant_id"] == tenant_id), None)
    assert match is not None
    assert round(match["balance_usd"], 2) == 3.0


def test_keys_mode_rejects_gateway_chat(client, monkeypatch):
    asyncio.run(_seed(credit_usd=5.0))
    monkeypatch.setattr(get_settings(), "openrouter_provisioning_key", "sk-or-provisioning")
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
    headers = _login(client, "owner@ai.test", "ai-password")
    r = client.post("/api/v1/ai/chat", headers=headers,
                    json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 400  # provisioning mode → use your own key directly
