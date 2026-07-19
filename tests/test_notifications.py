"""Outbound webhook notifications — signing, subscription routing, delivery
status capture, and the best-effort guarantee (a failing webhook never raises)."""

import asyncio
import hashlib
import hmac
import json

import httpx

from app.db import init_db, session_scope
from app.services.notifications import (
    DEPLOY_FAILED,
    DEPLOY_SUCCEEDED,
    NotificationService,
)


def _mock_transport(captured: list, *, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status)

    return httpx.MockTransport(handler)


def test_signature_is_hmac_sha256_over_body():
    body = b'{"event":"test","data":{}}'
    sig = NotificationService.sign("whsec_abc", body)
    expected = "sha256=" + hmac.new(b"whsec_abc", body, hashlib.sha256).hexdigest()
    assert sig == expected


def test_create_generates_secret_and_normalizes_events():
    async def go():
        await init_db()
        async with session_scope() as s:
            svc = NotificationService(s)
            a = await svc.create("t1", name="Slack", url="https://hooks.example/x")
            b = await svc.create("t1", name="Two", url="https://y", events="deploy.failed, deploy.succeeded")
            c = await svc.create("t1", name="Blank", url="https://z", events="")
            return a.secret, a.events, b.events, c.events

    secret, a_events, b_events, c_events = asyncio.run(go())
    assert secret.startswith("whsec_") and len(secret) > 10
    assert a_events == "*"
    assert b_events == "deploy.failed,deploy.succeeded"
    assert c_events == "*"


def test_dispatch_routes_only_to_subscribed_enabled_channels():
    captured: list = []

    async def go():

        await init_db()
        async with session_scope() as s:
            svc = NotificationService(s, transport=_mock_transport(captured))
            all_ch = await svc.create("t1", name="all", url="https://all.example/hook")
            only_fail = await svc.create("t1", name="fail", url="https://fail.example/hook", events="deploy.failed")
            disabled = await svc.create("t1", name="off", url="https://off.example/hook")
            disabled.enabled = False
            other_tenant = await svc.create("t2", name="other", url="https://other.example/hook")
            await s.flush()

            attempted = await svc.dispatch("t1", DEPLOY_SUCCEEDED, {"project": "blog"})
            return attempted, all_ch.url, only_fail.url, disabled.url, other_tenant.url

    attempted, all_url, fail_url, off_url, other_url = asyncio.run(go())
    urls = {str(r.url) for r in captured}
    assert attempted == 1  # only the "*" channel matches deploy.succeeded for t1
    assert all_url in urls
    assert fail_url not in urls  # not subscribed to succeeded
    assert off_url not in urls  # disabled
    assert other_url not in urls  # different tenant


def test_deliver_signs_body_and_records_ok():
    captured: list = []

    async def go():

        await init_db()
        async with session_scope() as s:
            svc = NotificationService(s, transport=_mock_transport(captured))
            ch = await svc.create("t1", name="c", url="https://c.example/hook")
            ok, label = await svc.deliver(ch, DEPLOY_SUCCEEDED, {"project": "blog"})
            return ok, label, ch.last_status, ch.secret

    ok, label, last_status, secret = asyncio.run(go())
    assert ok and label == "ok" and last_status == "ok"
    req = captured[0]
    assert req.headers["X-Tetra-Event"] == DEPLOY_SUCCEEDED
    # The signature header verifies against the exact body sent.
    assert req.headers["X-Tetra-Signature"] == NotificationService.sign(secret, req.content)
    assert json.loads(req.content) == {"event": DEPLOY_SUCCEEDED, "data": {"project": "blog"}}


def test_delivery_failure_is_recorded_not_raised():
    async def go():
        await init_db()
        async with session_scope() as s:
            svc = NotificationService(s, transport=_mock_transport([], status=500))
            ch = await svc.create("t1", name="c", url="https://c.example/hook")
            ok, label = await svc.deliver(ch, DEPLOY_FAILED, {})
            return ok, label, ch.last_status

    ok, label, last_status = asyncio.run(go())
    assert ok is False
    assert label == "http 500" and last_status == "http 500"


def test_unreachable_endpoint_is_swallowed():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    async def go():

        await init_db()
        async with session_scope() as s:
            svc = NotificationService(s, transport=httpx.MockTransport(boom))
            ch = await svc.create("t1", name="c", url="https://c.example/hook")
            # Must not raise.
            ok, label = await svc.deliver(ch, DEPLOY_FAILED, {})
            return ok, label

    ok, label = asyncio.run(go())
    assert ok is False and label == "unreachable"


def test_deploys_service_notify_helper_dispatches_best_effort():
    """The deploy path's _notify_deploy attempts delivery and never raises, even
    when the endpoint is unreachable."""
    from app.modules.deploys.service import DeploysService

    async def go():
        await init_db()
        async with session_scope() as s:
            await NotificationService(s).create("t1", name="x", url="http://127.0.0.1:9/hook")
        svc = DeploysService.__new__(DeploysService)  # skip heavy __init__; helper is self-contained
        await svc._notify_deploy("t1", "blog", "dep1", DEPLOY_SUCCEEDED, {"status": "ready"})
        async with session_scope() as s:
            ch = (await NotificationService(s).list_for_tenant("t1"))[0]
            return ch.last_status

    last_status = asyncio.run(go())
    assert last_status  # a delivery was attempted and its outcome recorded


def test_delete_scoped_to_tenant():
    async def go():
        await init_db()
        async with session_scope() as s:
            svc = NotificationService(s)
            ch = await svc.create("t1", name="c", url="https://c.example/hook")
            # Wrong tenant can't delete.
            assert await svc.delete("t2", ch.id) is False
            assert await svc.delete("t1", ch.id) is True
            assert await svc.get("t1", ch.id) is None

    asyncio.run(go())
