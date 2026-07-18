"""Mailcow write operations (Phase 2): domains, mailboxes, aliases, DKIM, ESP relay.

Direct-client tests over an injected httpx.MockTransport — request shapes follow the
verified spec in docs/providers/combined-api-reference.md (mailcow openapi.yaml).
Key gotcha under test: mailcow returns HTTP 200 with an envelope of
{type: success|danger|error} items — a 200 "danger" is a FAILURE.
"""

import asyncio
import json

import httpx
import pytest

from app.cache import TTLCache
from app.services.http import ProviderAPIError
from app.services.mailcow import MailcowClient, normalize_alias


def _client(handler, *, base_url="https://mail.test", api_key="k") -> MailcowClient:
    return MailcowClient(
        base_url=base_url,
        api_key=api_key,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
    )


def _ok(msg="done"):
    return httpx.Response(200, json=[{"type": "success", "msg": [msg], "log": []}])


# ── envelope handling ───────────────────────────────────────────────────────


def test_write_raises_on_danger_envelope_despite_http_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[{"type": "danger", "msg": ["domain_invalid", "bad..tld"], "log": []}]
        )

    with pytest.raises(ProviderAPIError) as err:
        asyncio.run(_client(handler).create_domain("bad..tld"))
    assert "domain_invalid" in str(err.value)


def test_write_accepts_object_envelope_variant():
    # The spec sometimes declares a bare object instead of an array — tolerate both.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "success", "msg": ["mailbox_added"]})

    asyncio.run(
        _client(handler).create_mailbox("info", "acme.test", password="s3cret-pass")
    )


def test_writes_require_configuration():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not be called")

    with pytest.raises(ProviderAPIError) as err:
        asyncio.run(_client(handler, base_url="", api_key="").create_domain("acme.test"))
    assert "not configured" in str(err.value)


# ── domains ─────────────────────────────────────────────────────────────────


def test_create_domain_posts_verified_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("X-API-Key")
        seen["body"] = json.loads(request.content)
        return _ok("domain_added")

    asyncio.run(_client(handler).create_domain("acme.test", description="Acme"))
    assert seen["url"] == "https://mail.test/api/v1/add/domain"
    assert seen["key"] == "k"
    body = seen["body"]
    assert body["domain"] == "acme.test"
    assert body["active"] == "1" and body["restart_sogo"] == "1"
    assert {"quota", "maxquota", "defquota", "mailboxes", "aliases"} <= set(body)


def test_delete_domain_posts_json_array():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok("domain_removed")

    asyncio.run(_client(handler).delete_domain("acme.test"))
    assert seen["url"] == "https://mail.test/api/v1/delete/domain"
    assert seen["body"] == ["acme.test"]


def test_domain_write_invalidates_domain_cache():
    async def go():
        client = _client(lambda r: _ok())
        await client.cache.set("mailcow:domains", ["stale"], 60)
        await client.create_domain("acme.test")
        return await client.cache.get("mailcow:domains")

    assert asyncio.run(go()) is None


# ── mailboxes ───────────────────────────────────────────────────────────────


def test_create_mailbox_sends_password_pair_and_quota():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok("mailbox_added")

    asyncio.run(
        _client(handler).create_mailbox(
            "info", "acme.test", name="Info", password="s3cret-pass", quota_mb=1024
        )
    )
    assert seen["url"] == "https://mail.test/api/v1/add/mailbox"
    body = seen["body"]
    assert body["local_part"] == "info" and body["domain"] == "acme.test"
    assert body["password"] == "s3cret-pass" and body["password2"] == "s3cret-pass"
    assert body["quota"] == "1024"


def test_delete_mailbox_posts_json_array():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok()

    asyncio.run(_client(handler).delete_mailbox("info@acme.test"))
    assert seen["url"] == "https://mail.test/api/v1/delete/mailbox"
    assert seen["body"] == ["info@acme.test"]


# ── aliases ─────────────────────────────────────────────────────────────────


def test_list_aliases_normalizes_and_caches():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json=[
                {"id": 6, "address": "sales@acme.test", "goto": "info@acme.test", "active": "1"},
                {"id": 7, "address": "@acme.test", "goto": "info@acme.test", "active": "0"},
            ],
        )

    async def go():
        client = _client(handler)
        first = await client.list_aliases()
        second = await client.list_aliases()  # cached
        return first, second

    first, second = asyncio.run(go())
    assert calls == ["https://mail.test/api/v1/get/alias/all"]
    assert first[0].id == 6 and first[0].domain == "acme.test"
    assert first[1].domain == "acme.test"  # catchall @domain
    assert not first[1].active
    assert [a.id for a in second] == [6, 7]


def test_create_and_delete_alias_shapes():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), json.loads(request.content)))
        return _ok()

    async def go():
        client = _client(handler)
        await client.create_alias("sales@acme.test", "info@acme.test")
        await client.delete_alias(6)

    asyncio.run(go())
    assert seen[0] == (
        "https://mail.test/api/v1/add/alias",
        {"address": "sales@acme.test", "goto": "info@acme.test", "active": "1"},
    )
    assert seen[1] == ("https://mail.test/api/v1/delete/alias", ["6"])


def test_normalize_alias_tolerates_string_ids():
    alias = normalize_alias({"id": "9", "address": "a@b.test", "goto": "c@b.test"})
    assert alias.id == 9 and alias.active is True


# ── DKIM ────────────────────────────────────────────────────────────────────


def test_get_dkim_returns_record_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://mail.test/api/v1/get/dkim/acme.test"
        return httpx.Response(
            200,
            json={"dkim_selector": "dkim", "dkim_txt": "v=DKIM1;k=rsa;p=MIIB", "length": "2048"},
        )

    dkim = asyncio.run(_client(handler).get_dkim("acme.test"))
    assert dkim["dkim_selector"] == "dkim"
    assert dkim["dkim_txt"].startswith("v=DKIM1")


def test_generate_dkim_posts_domain_selector_size():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok("dkim_added")

    asyncio.run(_client(handler).generate_dkim("acme.test"))
    assert seen["url"] == "https://mail.test/api/v1/add/dkim"
    assert seen["body"] == {"domains": "acme.test", "dkim_selector": "dkim", "key_size": "2048"}


# ── ESP relay (sender-dependent transports) ─────────────────────────────────


def test_create_relayhost_and_assign_to_domain():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), json.loads(request.content)))
        return _ok()

    async def go():
        client = _client(handler)
        await client.create_relayhost("smtp.postmarkapp.com:587", "apikey", "secret")
        await client.assign_relayhost("acme.test", 2)

    asyncio.run(go())
    assert seen[0] == (
        "https://mail.test/api/v1/add/relayhost",
        {"hostname": "smtp.postmarkapp.com:587", "username": "apikey", "password": "secret"},
    )
    assert seen[1] == (
        "https://mail.test/api/v1/edit/domain",
        {"items": ["acme.test"], "attr": {"relayhost": "2"}},
    )


def test_list_relayhosts_returns_raw_entries():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://mail.test/api/v1/get/relayhost/all"
        return httpx.Response(200, json=[{"id": 2, "hostname": "smtp.postmarkapp.com:587"}])

    hosts = asyncio.run(_client(handler).list_relayhosts())
    assert hosts[0]["id"] == 2


# ── mailbox usage + edit ────────────────────────────────────────────────────


def test_list_mailboxes_captures_quota_used_and_percent():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://mail.test/api/v1/get/mailbox/all"
        return httpx.Response(
            200,
            json=[
                {"username": "a@acme.test", "quota": 1000, "quota_used": 250, "messages": 3},
                {"username": "b@acme.test", "quota": 0, "quota_used": 0},
            ],
        )

    boxes = asyncio.run(_client(handler).list_mailboxes())
    assert boxes[0].quota_used_bytes == 250 and boxes[0].percent_used == 25
    # divide-by-zero guard: an unlimited (quota 0) mailbox reports 0%, not a crash
    assert boxes[1].percent_used == 0


def test_edit_mailbox_sends_only_supplied_attrs():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok("mailbox_modified")

    asyncio.run(
        _client(handler).edit_mailbox("info@acme.test", quota_mb=2048, active=False)
    )
    assert seen["url"] == "https://mail.test/api/v1/edit/mailbox"
    assert seen["body"] == {
        "items": ["info@acme.test"],
        "attr": {"quota": "2048", "active": "0"},
    }


def test_edit_mailbox_password_is_paired():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok()

    asyncio.run(_client(handler).edit_mailbox("info@acme.test", password="newpass12"))
    assert seen["body"]["attr"] == {"password": "newpass12", "password2": "newpass12"}


def test_edit_mailbox_rejects_empty_change():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not call mailcow with no attrs")

    with pytest.raises(ProviderAPIError):
        asyncio.run(_client(handler).edit_mailbox("info@acme.test"))


# ── app passwords ───────────────────────────────────────────────────────────


def test_create_app_password_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok("app_passwd_added")

    asyncio.run(
        _client(handler).create_app_password(
            "info@acme.test", app_name="Thunderbird", password="abcd-efgh"
        )
    )
    assert seen["url"] == "https://mail.test/api/v1/add/app-passwd"
    body = seen["body"]
    assert body["username"] == "info@acme.test" and body["app_name"] == "Thunderbird"
    assert body["app_passwd"] == "abcd-efgh" and body["app_passwd2"] == "abcd-efgh"
    assert body["protocols"] == ["imap_access", "smtp_access"]


def test_list_and_delete_app_passwords():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert str(request.url).endswith("/get/app-passwd/all/info@acme.test")
            return httpx.Response(200, json=[{"id": 9, "name": "Thunderbird", "active": "1"}])
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok()

    async def go():
        client = _client(handler)
        items = await client.list_app_passwords("info@acme.test")
        await client.delete_app_password(9)
        return items

    items = asyncio.run(go())
    assert items[0].id == 9 and items[0].name == "Thunderbird"
    assert seen["url"] == "https://mail.test/api/v1/delete/app-passwd"
    assert seen["body"] == ["9"]


# ── quarantine ──────────────────────────────────────────────────────────────


def test_list_quarantine_normalizes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://mail.test/api/v1/get/quarantine/all"
        return httpx.Response(
            200,
            json=[
                {"id": 4, "subject": "Win a prize", "sender": "spam@x.tld",
                 "rcpt": "info@acme.test", "score": "12.5", "created": 1700000000},
            ],
        )

    items = asyncio.run(_client(handler).list_quarantine())
    assert items[0].id == 4 and items[0].rcpt == "info@acme.test"
    assert items[0].score == 12.5


def test_quarantine_action_and_delete_shapes():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), json.loads(request.content)))
        return _ok()

    async def go():
        client = _client(handler)
        await client.act_on_quarantine([4, 5], "release")
        await client.delete_quarantine([7])

    asyncio.run(go())
    assert seen[0] == (
        "https://mail.test/api/v1/edit/qitem",
        {"items": ["4", "5"], "attr": {"action": "release"}},
    )
    assert seen[1] == ("https://mail.test/api/v1/delete/qitem", ["7"])


def test_quarantine_action_rejects_unknown_action():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not call mailcow with a bad action")

    with pytest.raises(ProviderAPIError):
        asyncio.run(_client(handler).act_on_quarantine([1], "nuke"))
