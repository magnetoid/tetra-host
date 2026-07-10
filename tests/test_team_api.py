import asyncio

from app.db import session_scope
from app.models import AdminUser, Tenant
from app.modules.auth.service import AuthService


async def _seed() -> str:
    async with session_scope() as session:
        auth = AuthService(session)
        tenant = Tenant(name="Acme", slug="acme", status="active")
        session.add(tenant)
        await session.flush()
        # role defaults to ROLE_OWNER.
        session.add(AdminUser(
            tenant_id=tenant.id, email="owner@acme.test", full_name="Acme Owner",
            password_hash=auth.hash_password("owner-password"), is_active=True,
        ))
        # A second, isolated tenant to prove scoping.
        other = Tenant(name="Other", slug="other", status="active")
        session.add(other)
        await session.flush()
        session.add(AdminUser(
            tenant_id=other.id, email="owner@other.test", full_name="Other Owner",
            password_hash=auth.hash_password("other-password"), is_active=True,
        ))
        return tenant.id


def _login(client, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_invite_accept_flow(client):
    asyncio.run(_seed())
    owner = _login(client, "owner@acme.test", "owner-password")

    # Owner mints an invite → gets a one-time token + share URL.
    created = client.post("/api/v1/team/invites", headers=owner,
                          json={"email": "mate@acme.test", "role": "member"})
    assert created.status_code == 200, created.text
    body = created.json()
    token = body["token"]
    assert token and body["accept_url"].endswith(token)
    assert body["invite"]["status"] == "pending"

    # Team now shows the owner + a pending invite.
    team = client.get("/api/v1/team", headers=owner).json()
    assert len(team["members"]) == 1
    assert len(team["invites"]) == 1

    # Public preview resolves who/what the invite is for.
    preview = client.get("/api/v1/auth/invite", params={"token": token})
    assert preview.status_code == 200
    assert preview.json() == {"tenant_name": "Acme", "email": "mate@acme.test", "role": "member"}

    # Redeem it → a member login is created and signed in.
    accepted = client.post("/api/v1/auth/accept-invite",
                           json={"token": token, "full_name": "Team Mate", "password": "mate-password"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["admin"]["role"] == "member"
    assert accepted.json()["token"]

    # Owner now sees two members and no pending invites.
    team = client.get("/api/v1/team", headers=owner).json()
    assert len(team["members"]) == 2
    assert len(team["invites"]) == 0

    # Single-use: the same token can't be redeemed twice.
    reuse = client.post("/api/v1/auth/accept-invite",
                        json={"token": token, "full_name": "x", "password": "xxxxxxxxxx"})
    assert reuse.status_code == 404


def test_rbac_and_guardrails(client):
    asyncio.run(_seed())
    owner = _login(client, "owner@acme.test", "owner-password")

    # Invalid role rejected.
    assert client.post("/api/v1/team/invites", headers=owner,
                       json={"email": "x@acme.test", "role": "owner"}).status_code == 400

    # Create a member via invite.
    token = client.post("/api/v1/team/invites", headers=owner,
                        json={"email": "mate@acme.test", "role": "member"}).json()["token"]
    client.post("/api/v1/auth/accept-invite",
                json={"token": token, "full_name": "Mate", "password": "mate-password"})
    mate = _login(client, "mate@acme.test", "mate-password")
    member_id = client.get("/api/v1/auth/me", headers=mate).json()["id"]

    # Members cannot manage the team.
    assert client.post("/api/v1/team/invites", headers=mate,
                       json={"email": "z@acme.test", "role": "member"}).status_code == 403

    # Owner can promote the member to admin.
    promoted = client.post(f"/api/v1/team/members/{member_id}/role", headers=owner,
                           json={"role": "admin"})
    assert promoted.status_code == 200 and promoted.json()["role"] == "admin"

    # Owner cannot remove themselves.
    owner_id = client.get("/api/v1/auth/me", headers=owner).json()["id"]
    assert client.delete(f"/api/v1/team/members/{owner_id}", headers=owner).status_code == 400

    # A tenant cannot reach across into another tenant's member.
    other_owner = _login(client, "owner@other.test", "other-password")
    assert client.post(f"/api/v1/team/members/{member_id}/role", headers=other_owner,
                       json={"role": "member"}).status_code == 404

    # Removing a member deactivates them → they can no longer sign in.
    removed = client.delete(f"/api/v1/team/members/{member_id}", headers=owner)
    assert removed.status_code == 200 and removed.json()["is_active"] is False
    assert client.post("/api/v1/auth/login",
                       json={"email": "mate@acme.test", "password": "mate-password"}).status_code == 401


def test_invalid_token_preview_and_accept(client):
    asyncio.run(_seed())
    assert client.get("/api/v1/auth/invite", params={"token": "nope"}).status_code == 404
    assert client.post("/api/v1/auth/accept-invite",
                       json={"token": "nope", "full_name": "x", "password": "xxxxxxxxxx"}).status_code == 404
