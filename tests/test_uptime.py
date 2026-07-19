"""Uptime monitoring — probing, state transitions, and transition-only alerting."""

import asyncio

import httpx

from app.db import init_db, session_scope
from app.models.uptime import UPTIME_DOWN, UPTIME_UNKNOWN, UPTIME_UP
from app.services.uptime import APP_DOWN, APP_UP, UptimeService


def _transport(status: int | None):
    """A transport returning ``status``; None raises a connection error (down)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if status is None:
            raise httpx.ConnectError("no route")
        return httpx.Response(status)

    return httpx.MockTransport(handler)


def test_probe_classifies_up_down_and_unreachable():
    async def go():
        await init_db()
        async with session_scope() as s:
            up = await UptimeService(s, transport=_transport(200)).probe("https://x")
            redirect = await UptimeService(s, transport=_transport(302)).probe("https://x")
            err = await UptimeService(s, transport=_transport(503)).probe("https://x")
            dead = await UptimeService(s, transport=_transport(None)).probe("https://x")
            return up[0], redirect[0], err[0], dead[0]

    up, redirect, err, dead = asyncio.run(go())
    assert up == UPTIME_UP
    assert redirect == UPTIME_UP  # 3xx counts as up
    assert err == UPTIME_DOWN
    assert dead == UPTIME_DOWN


def test_should_alert_transition_rules():
    s = UptimeService
    assert s._should_alert(UPTIME_UP, UPTIME_DOWN) is True
    assert s._should_alert(UPTIME_DOWN, UPTIME_UP) is True
    assert s._should_alert(UPTIME_UNKNOWN, UPTIME_DOWN) is True  # first check finds it down
    assert s._should_alert(UPTIME_UNKNOWN, UPTIME_UP) is False  # came online — no alarm
    assert s._should_alert(UPTIME_UP, UPTIME_UP) is False  # steady state


def test_check_one_records_and_alerts_only_on_transition():
    events: list = []

    async def notify(tenant_id, event, payload):
        events.append((tenant_id, event, payload["status"]))

    async def go():
        await init_db()
        async with session_scope() as s:
            svc_down = UptimeService(s, transport=_transport(None))
            svc_up = UptimeService(s, transport=_transport(200))
            mon = await svc_up.create("t1", name="site", url="https://site.example")

            # First check: up. unknown→up, no alert. State recorded.
            await svc_up.check_one(mon, notify)
            assert mon.status == UPTIME_UP and mon.last_detail
            first = list(events)

            # Goes down: up→down → app.down alert.
            await svc_down.check_one(mon, notify)
            # Still down: down→down, no new alert.
            await svc_down.check_one(mon, notify)
            # Recovers: down→up → app.up alert.
            await svc_up.check_one(mon, notify)
            return first, events, mon.status

    first, events, final = asyncio.run(go())
    assert first == []  # unknown→up did not alert
    assert [e[1] for e in events] == [APP_DOWN, APP_UP]
    assert final == UPTIME_UP


def test_run_all_due_only_enabled_and_returns_count():
    async def go():
        await init_db()
        async with session_scope() as s:
            svc = UptimeService(s, transport=_transport(200))
            await svc.create("t1", name="a", url="https://a")
            b = await svc.create("t1", name="b", url="https://b")
            b.enabled = False
            await s.flush()
            ran = await svc.run_all_due(notify=lambda *a: _noop())
            return ran

    assert asyncio.run(go()) == 1


async def _noop():
    return None


def test_scheduler_run_uptime_checks_wrapper():
    """The scheduler entrypoint probes seeded monitors and returns a count."""
    from app.services.scheduler import run_uptime_checks

    async def go():
        await init_db()
        async with session_scope() as s:
            await UptimeService(s).create("t1", name="dead", url="http://127.0.0.1:9/")
        return await run_uptime_checks()

    assert asyncio.run(go()) == 1


def test_delete_scoped_to_tenant():
    async def go():
        await init_db()
        async with session_scope() as s:
            svc = UptimeService(s)
            m = await svc.create("t1", name="a", url="https://a")
            assert await svc.delete("t2", m.id) is False
            assert await svc.delete("t1", m.id) is True
            assert await svc.get("t1", m.id) is None

    asyncio.run(go())
