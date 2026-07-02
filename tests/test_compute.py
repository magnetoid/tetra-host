"""Live per-app compute stats: docker-stats parsing, engine resolution, API."""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.services.compute import parse_compute_samples, parse_size_to_bytes
from app.services.docker_engine import DockerEngine

_RAW = [
    {
        "Name": "blog-app-1", "CPUPerc": "5.00%",
        "MemUsage": "100MiB / 512MiB", "MemPerc": "20.00%",
        "NetIO": "1kB / 2kB", "PIDs": "3",
    }
]


# ── Parser (pure) ──────────────────────────────────────────────────────────


def test_parse_size_binary_and_decimal_and_junk():
    assert parse_size_to_bytes("512MiB") == 512 * 1024**2
    assert parse_size_to_bytes("1.5GB") == 1.5e9
    assert parse_size_to_bytes("0B") == 0.0
    assert parse_size_to_bytes("--") == 0.0
    assert parse_size_to_bytes("") == 0.0


def test_parse_compute_samples_normalizes():
    [s] = parse_compute_samples(
        [{
            "Name": "blog-app-1", "CPUPerc": "12.34%",
            "MemUsage": "45.7MiB / 512MiB", "MemPerc": "8.93%",
            "NetIO": "1.2kB / 3.4MB", "PIDs": "7",
        }]
    )
    assert s.name == "blog-app-1"
    assert s.cpu_percent == 12.34
    assert s.mem_used_mb == round(45.7 * 1024**2 / 1e6, 2)
    assert s.mem_limit_mb == round(512 * 1024**2 / 1e6, 2)
    assert s.mem_percent == 8.93
    assert s.net_rx_mb == round(1.2e3 / 1e6, 2)
    assert s.net_tx_mb == round(3.4e6 / 1e6, 2)
    assert s.pids == 7


def test_parse_handles_missing_bad_and_empty():
    [s] = parse_compute_samples([{"Name": "x"}])
    assert s.cpu_percent == 0.0 and s.mem_used_mb == 0.0 and s.pids == 0
    assert parse_compute_samples([]) == []
    assert parse_compute_samples(["not-a-dict"]) == []


# ── Engine resolution (fake runner, no docker) ─────────────────────────────


def test_engine_stats_for_project_resolves_ids_then_stats():
    seen: list[list[str]] = []

    async def runner(argv, stdin, env):
        seen.append(argv)
        if "ps" in argv:
            return 0, '[{"ID": "c1", "Name": "blog-app-1"}]', ""
        if "stats" in argv:
            assert "c1" in argv  # resolved id passed through
            return 0, '{"Name": "blog-app-1", "CPUPerc": "1.00%", "MemUsage": "10MiB / 20MiB", "MemPerc": "50.00%", "NetIO": "0B / 0B", "PIDs": "2"}', ""
        return 0, "", ""

    engine = DockerEngine(runner=runner)
    raw = asyncio.run(engine.stats_for_project("blog"))
    assert raw and raw[0]["Name"] == "blog-app-1"
    assert any("stats" in argv for argv in seen)


# ── Endpoint (tenant-scoped) ───────────────────────────────────────────────


async def _seed(*, slug: str, email: str, app: str) -> None:
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
                password_hash=auth.hash_password("cmp-pass"), is_active=True,
            )
        )
        session.add(
            TenantResource(
                tenant_id=tenant.id, provider=PROVIDER_DOCKER,
                resource_type=RESOURCE_TYPE_APP, external_id=app, display_name=app,
            )
        )


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "cmp-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_compute_endpoint_returns_samples_and_totals(client, monkeypatch):
    asyncio.run(_seed(slug="cmp", email="owner@cmp.test", app="blog"))

    async def fake_stats(self, project):
        assert project == "blog"
        return _RAW

    monkeypatch.setattr(DockerEngine, "stats_for_project", fake_stats)
    headers = _login(client, "owner@cmp.test")
    r = client.get("/api/v1/apps/blog/compute", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["project"] == "blog"
    assert data["cpu_percent"] == 5.0
    assert data["samples"][0]["name"] == "blog-app-1"
    assert data["samples"][0]["mem_used_mb"] == round(100 * 1024**2 / 1e6, 2)


def test_compute_denies_foreign_app(client, monkeypatch):
    asyncio.run(_seed(slug="c2", email="owner@c2.test", app="mine"))

    async def fake_stats(self, project):  # should never be reached
        raise AssertionError("stats fetched for an unowned app")

    monkeypatch.setattr(DockerEngine, "stats_for_project", fake_stats)
    headers = _login(client, "owner@c2.test")
    r = client.get("/api/v1/apps/other/compute", headers=headers)
    assert r.status_code == 403
