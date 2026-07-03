"""AI-assisted build-failure diagnosis: pure heuristic taxonomy + gated LLM enrichment."""

import asyncio

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.deployment import STATUS_ERROR, STATUS_READY, Deployment
from app.modules.auth.service import AuthService
from app.modules.deploys.service import DeploysService
from app.services.build_diagnostics import Diagnosis, analyze_build_log


# ── Pure heuristic analyzer (deterministic, no network) ────────────────────


def test_no_buildpack_signature():
    log = "→ cloning\nNixpacks was unable to generate a build plan for this app.\n✗ failed"
    d = analyze_build_log(log, status=STATUS_ERROR, error="build failed")
    assert d.source == "heuristic" and d.confidence == "high"
    assert d.category == "build-config"
    assert any("Dockerfile" in fix for fix in d.suggested_fixes)


def test_dependency_conflict_signature():
    log = "npm error ERESOLVE could not resolve\nnpm error peer dependency conflict"
    d = analyze_build_log(log, status=STATUS_ERROR, error="")
    assert d.category == "dependencies"
    assert d.likely_causes and d.confidence == "high"


def test_oom_signature():
    log = "Compiling assets...\nContainer killed: signal: killed (out of memory)"
    d = analyze_build_log(log, status=STATUS_ERROR, error="")
    assert d.category == "resources"
    assert any("memory" in c.lower() for c in d.likely_causes)


def test_port_binding_signature():
    log = "container started\nno open ports detected, the app is not listening on $PORT"
    d = analyze_build_log(log, status=STATUS_ERROR, error="")
    assert d.category == "runtime"
    assert any("PORT" in fix for fix in d.suggested_fixes)


def test_git_auth_signature():
    log = "→ cloning https://github.com/x/private\nfatal: Authentication failed for repository"
    d = analyze_build_log(log, status=STATUS_ERROR, error="")
    assert d.category == "source"


def test_unknown_failure_is_low_confidence():
    d = analyze_build_log("some totally opaque failure", status=STATUS_ERROR, error="boom")
    assert d.category == "unknown" and d.confidence == "low"
    assert d.suggested_fixes  # still offers a next step


def test_success_has_nothing_to_explain():
    d = analyze_build_log("✓ built\n✓ live", status=STATUS_READY, error="")
    assert d.category == "none" and d.likely_causes == []


def test_diagnosis_to_dict_round_trips():
    d = Diagnosis(
        summary="s", category="c", likely_causes=["a"], suggested_fixes=["b"],
        confidence="high", source="heuristic",
    )
    assert d.to_dict()["likely_causes"] == ["a"]


# ── Service (tenant-scoped, AI enrichment injectable + fallback) ───────────


async def _seed_with_deployment(*, slug: str, email: str, status: str, log: str, error: str = "") -> tuple[str, str]:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id, email=email, full_name="Owner",
                password_hash=auth.hash_password("diag-pass"), is_active=True,
            )
        )
        dep = Deployment(
            tenant_id=tenant.id, project="blog", status=status, log=log, error=error,
        )
        session.add(dep)
        await session.flush()
        return tenant.id, dep.id


def test_explain_uses_heuristic_when_no_diagnoser(client):
    async def go():
        tenant_id, dep_id = await _seed_with_deployment(
            slug="ex", email="o@ex.test", status=STATUS_ERROR,
            log="Nixpacks was unable to generate a build plan", error="build failed",
        )
        service = DeploysService(request=object())
        async with session_scope() as session:
            diag = await service.explain_deployment(session, tenant_id, dep_id, diagnoser=None)
        assert diag is not None and diag.source == "heuristic"
        assert diag.category == "build-config"

    asyncio.run(go())


def test_explain_prefers_ai_diagnoser_when_available(client):
    async def fake_diagnoser(log, status, error):
        return Diagnosis(
            summary="AI says: missing Dockerfile", category="build-config",
            likely_causes=["no Dockerfile"], suggested_fixes=["add one"],
            confidence="high", source="ai",
        )

    async def go():
        tenant_id, dep_id = await _seed_with_deployment(
            slug="ai", email="o@ai.test", status=STATUS_ERROR, log="boom",
        )
        service = DeploysService(request=object())
        async with session_scope() as session:
            diag = await service.explain_deployment(
                session, tenant_id, dep_id, diagnoser=fake_diagnoser
            )
        assert diag.source == "ai" and "AI says" in diag.summary

    asyncio.run(go())


def test_explain_falls_back_to_heuristic_when_ai_raises(client):
    async def broken_diagnoser(log, status, error):
        raise RuntimeError("anthropic exploded")

    async def go():
        tenant_id, dep_id = await _seed_with_deployment(
            slug="fb", email="o@fb.test", status=STATUS_ERROR,
            log="npm error ERESOLVE could not resolve",
        )
        service = DeploysService(request=object())
        async with session_scope() as session:
            diag = await service.explain_deployment(
                session, tenant_id, dep_id, diagnoser=broken_diagnoser
            )
        assert diag.source == "heuristic" and diag.category == "dependencies"

    asyncio.run(go())


def test_explain_skips_ai_for_successful_deployment(client):
    """A successful build has nothing to diagnose — the AI enricher must not be invoked."""
    calls: list[tuple] = []

    async def spy_diagnoser(log, status, error):
        calls.append((status, error))
        return Diagnosis(summary="fabricated failure", category="x", confidence="high", source="ai")

    async def go():
        tenant_id, dep_id = await _seed_with_deployment(
            slug="ok", email="o@ok.test", status=STATUS_READY, log="✓ built\n✓ live",
        )
        service = DeploysService(request=object())
        async with session_scope() as session:
            diag = await service.explain_deployment(
                session, tenant_id, dep_id, diagnoser=spy_diagnoser
            )
        assert calls == []  # AI never called for a non-failed deployment
        assert diag.source == "heuristic" and diag.category == "none"

    asyncio.run(go())


def test_explain_returns_none_for_other_tenant(client):
    async def go():
        _, dep_id = await _seed_with_deployment(
            slug="t1", email="o@t1.test", status=STATUS_ERROR, log="x",
        )
        other_id, _ = await _seed_with_deployment(
            slug="t2", email="o@t2.test", status=STATUS_ERROR, log="y",
        )
        service = DeploysService(request=object())
        async with session_scope() as session:
            diag = await service.explain_deployment(session, other_id, dep_id, diagnoser=None)
        assert diag is None

    asyncio.run(go())


# ── API (GET /deploys/{id}/explain, tenant-scoped) ─────────────────────────


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "diag-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_explain_endpoint_returns_diagnosis(client, monkeypatch):
    # No ANTHROPIC_API_KEY in the test env → deterministic heuristic path.
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "", raising=False)
    tenant_id, dep_id = asyncio.run(
        _seed_with_deployment(
            slug="ep", email="o@ep.test", status=STATUS_ERROR,
            log="Nixpacks was unable to generate a build plan", error="build failed",
        )
    )
    headers = _login(client, "o@ep.test")
    r = client.get(f"/api/v1/deploys/{dep_id}/explain", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["deployment_id"] == dep_id
    assert body["category"] == "build-config"
    assert body["source"] == "heuristic"
    assert body["suggested_fixes"]


def test_explain_endpoint_404_for_unknown(client):
    asyncio.run(_seed_with_deployment(slug="nf", email="o@nf.test", status=STATUS_ERROR, log="x"))
    headers = _login(client, "o@nf.test")
    assert client.get("/api/v1/deploys/does-not-exist/explain", headers=headers).status_code == 404
