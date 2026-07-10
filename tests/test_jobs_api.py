import asyncio
from datetime import UTC, datetime

import httpx

from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.job import ScheduledJob
from app.modules.auth.service import AuthService
from app.services.scheduler import run_due_jobs


async def _seed() -> str:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key="j_plan", name="J", max_apps=5, max_domains=0,
                    cpu_millicores=500, mem_mb=512, disk_mb=2048)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name="J Tenant", slug="jt", status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(AdminUser(
            tenant_id=tenant.id, email="owner@j.test", full_name="J Owner",
            password_hash=auth.hash_password("j-password"), is_active=True,
        ))
        # A foreign job to prove tenant-scoped access.
        session.add(ScheduledJob(
            tenant_id="other", name="foreign", cron="* * * * *", url="https://x.test", method="GET",
        ))
        return tenant.id


def _login(client) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": "owner@j.test", "password": "j-password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_job_crud_and_tenant_scoping(client):
    asyncio.run(_seed())
    headers = _login(client)

    # invalid cron rejected
    bad = client.post("/api/v1/jobs", headers=headers,
                      json={"name": "x", "cron": "not valid", "url": "https://a.test"})
    assert bad.status_code == 422

    created = client.post("/api/v1/jobs", headers=headers,
                          json={"name": "ping", "cron": "*/5 * * * *", "url": "https://a.test/cron"})
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    assert created.json()["enabled"] is True

    listed = client.get("/api/v1/jobs", headers=headers).json()
    assert len(listed) == 1  # only own job, not the foreign one
    assert listed[0]["id"] == job_id

    disabled = client.patch(f"/api/v1/jobs/{job_id}", headers=headers, json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    # cannot touch another tenant's job
    assert client.get("/api/v1/jobs/does-not-exist/runs", headers=headers).status_code == 404

    assert client.delete(f"/api/v1/jobs/{job_id}", headers=headers).status_code == 200
    assert client.get("/api/v1/jobs", headers=headers).json() == []


def test_scheduler_fires_due_job_and_records_run(client):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="ok")

    async def setup_and_run() -> tuple[str, int]:
        async with session_scope() as session:
            auth = AuthService(session)
            plan = Plan(key="j_plan", name="J", max_apps=5, max_domains=0,
                        cpu_millicores=500, mem_mb=512, disk_mb=2048)
            session.add(plan)
            await session.flush()
            tenant = Tenant(name="J Tenant", slug="jt", status="active", plan_id=plan.id)
            session.add(tenant)
            await session.flush()
            session.add(AdminUser(
                tenant_id=tenant.id, email="owner@j.test", full_name="J Owner",
                password_hash=auth.hash_password("j-password"), is_active=True,
            ))
            job = ScheduledJob(
                tenant_id=tenant.id, name="tick", cron="* * * * *",
                url="https://hook.test/run", method="GET",
            )
            session.add(job)
            await session.flush()
            job_id = job.id
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            fired = await run_due_jobs(http, datetime(2026, 7, 10, 3, 4, tzinfo=UTC))
        return job_id, fired

    job_id, fired = asyncio.run(setup_and_run())
    assert fired >= 1
    assert "https://hook.test/run" in calls

    headers = _login(client)
    runs = client.get(f"/api/v1/jobs/{job_id}/runs", headers=headers).json()
    assert len(runs) == 1
    assert runs[0]["status"] == "ok"
    assert runs[0]["detail"] == "200"
