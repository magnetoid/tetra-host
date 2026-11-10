"""Coolify → engine importer: plan / stage / cutover / rollback against a fake Docker host."""

import asyncio
import json
import uuid

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db.session import close_db, init_db, session_scope
from app.models import AuditEvent, Deployment, ImportRun, Tenant, TenantResource
from app.models.import_run import (
    IMPORT_FAILED,
    IMPORT_LIVE,
    IMPORT_PLANNED,
    IMPORT_ROLLED_BACK,
    IMPORT_STAGED,
)
from app.modules.importers.service import STAGE_PORT_OFFSET, CoolifyImporter, ImporterError
from app.services.docker_engine import DockerEngine
from app.services.secrets import decrypt
from tests.test_importer_compose import ENV, SOURCE, UUID

# What answers on each published port while a stack is up.
ANSWERS = {9140: "http:200", 9141: "http:404", 9146: "tcp"}


class FakeHost:
    """Just enough of `docker` for the importer: files, volumes, images, compose stacks."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.volumes = {f"{UUID}_mtio-postgres-data"}
        self.images = {f"{UUID}_mtio-web:abc123", f"{UUID}_mtio-mailer:abc123", "kong:2.8.1"}
        self.running = {UUID}
        self.stacks: dict[str, str] = {}
        self.fail_up: set[str] = set()

    async def __call__(self, argv, stdin, env):
        args = argv[1:]
        self.calls.append(args)
        if args[:2] == ["run", "--rm"]:
            if "cat" in args:
                target = args[-1]
                if target.endswith("docker-compose.yaml"):
                    return 0, SOURCE, ""
                if target.endswith(".env"):
                    return 0, ENV, ""
                return 1, "", "no such file"
            if "du" in args:
                return 0, "64\t/v\n", ""
            return 0, "", ""
        if args[:2] == ["volume", "inspect"]:
            return (0, "[]", "") if args[2] in self.volumes else (1, "", "no such volume")
        if args[:2] == ["volume", "create"]:
            self.volumes.add(args[2])
            return 0, args[2], ""
        if args[:2] == ["volume", "rm"]:
            self.volumes.discard(args[2])
            return 0, "", ""
        if args[:2] == ["image", "inspect"]:
            return (0, "sha256:x", "") if args[-1] in self.images else (1, "", "no such image")
        if args[0] == "tag":
            self.images.add(args[2])
            return 0, "", ""
        if args[0] == "compose":
            project, verb = args[2], args[3]
            if verb == "-f":  # compose -p X -f - up -d
                if project in self.fail_up:
                    return 1, "", "boom"
                self.stacks[project] = stdin
                self.running.add(project)
            elif verb == "stop":
                self.running.discard(project)
            elif verb == "start":
                self.running.add(project)
            elif verb == "down":
                self.running.discard(project)
                self.stacks.pop(project, None)
            return 0, "", ""
        return 1, "", f"unexpected docker call {args}"

    async def probe(self, port: int) -> str:
        base = port - STAGE_PORT_OFFSET if port >= STAGE_PORT_OFFSET else port
        if base not in ANSWERS:
            return "closed"
        if port >= STAGE_PORT_OFFSET:
            up = "mtio-staging" in self.running
        else:
            up = UUID in self.running or "mtio" in self.running
        return ANSWERS[base] if up else "closed"


async def _no_sleep(_: float) -> None:
    return None


def _importer(fake: FakeHost) -> CoolifyImporter:
    return CoolifyImporter(
        engine=DockerEngine(runner=fake),
        probe=fake.probe,
        sleep=_no_sleep,
        stacks_dir="/srv/stacks",
        wait_seconds=0.05,
        poll_seconds=0,
    )


async def _tenant_id() -> str:
    await init_db()
    async with session_scope() as session:
        tenant = Tenant(name="Platform", slug=f"platform-{uuid.uuid4().hex[:8]}", status="active")
        session.add(tenant)
        await session.flush()
        return tenant.id


async def _plan(importer: CoolifyImporter, tenant_id: str, **kwargs) -> str:
    async with session_scope() as session:
        run = await importer.plan(
            session, tenant_id=tenant_id, actor="ops@example.com",
            app_uuid=UUID, project="mtio", **kwargs,
        )
        return run.id


async def _act(importer: CoolifyImporter, tenant_id: str, run_id: str, action: str) -> None:
    async with session_scope() as session:
        await importer.request(
            session, tenant_id=tenant_id, actor="ops@example.com", run_id=run_id, action=action
        )
    await importer.execute(run_id, action)


async def _run(run_id: str) -> ImportRun:
    async with session_scope() as session:
        run = await session.get(ImportRun, run_id)
        session.expunge(run)
        return run


@pytest.fixture
def actions_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)


def test_plan_records_summary_and_encrypts_source(actions_on):
    fake = FakeHost()

    async def main():
        tenant_id = await _tenant_id()
        run_id = await _plan(_importer(fake), tenant_id)
        run = await _run(run_id)
        async with session_scope() as session:
            audit = await session.scalar(select(AuditEvent).where(AuditEvent.action == "import.plan"))
        await close_db()
        return run, audit

    run, audit = asyncio.run(main())
    assert run.state == IMPORT_PLANNED
    s = run.summary
    assert s["stage_exclude"] == ["mtio-mailer"]
    assert s["image_overrides"]["mtio-web"] == "mtio-mtio-web:imported-abc123"
    assert {p["host_port"] for p in s["ports"]} == {9140, 9141, 9146}
    assert s["volumes"][0]["target"] == "mtio_mtio-postgres-data"
    assert s["volumes"][0]["stage_target"] == "mtio-staging_mtio-postgres-data"
    assert s["binds"] == ["init.sql", "scripts/kong.yml"]
    # Secrets never land in the readable summary, only in the encrypted blob.
    assert "p@ss$word" not in json.dumps(s)
    assert json.loads(decrypt(run.secret_blob))["env"] == ENV
    assert audit is not None and audit.target == "mtio"


def test_plan_rejects_missing_image_and_volume(actions_on):
    async def main(fake):
        tenant_id = await _tenant_id()
        try:
            await _plan(_importer(fake), tenant_id)
        finally:
            await close_db()

    no_image = FakeHost()
    no_image.images.discard(f"{UUID}_mtio-web:abc123")
    with pytest.raises(ImporterError, match="not on this host"):
        asyncio.run(main(no_image))
    no_volume = FakeHost()
    no_volume.volumes.clear()
    with pytest.raises(ImporterError, match="does not exist"):
        asyncio.run(main(no_volume))


def test_stage_then_cutover_then_rollback(actions_on):
    fake = FakeHost()
    importer = _importer(fake)

    async def main():
        tenant_id = await _tenant_id()
        run_id = await _plan(importer, tenant_id)

        await _act(importer, tenant_id, run_id, "stage")
        staged = await _run(run_id)
        assert staged.state == IMPORT_STAGED, staged.log
        assert "mtio-mailer" not in yaml.safe_load(fake.stacks["mtio-staging"])["services"]
        assert "127.0.0.1:19140:80" in fake.stacks["mtio-staging"]
        assert UUID in fake.running  # live app untouched by the trial copy

        await _act(importer, tenant_id, run_id, "cutover")
        live = await _run(run_id)
        assert live.state == IMPORT_LIVE, live.log
        assert UUID not in fake.running and "mtio" in fake.running
        assert "mtio-mailer" in yaml.safe_load(fake.stacks["mtio"])["services"]  # the real stack keeps its worker
        assert "mtio-staging" not in fake.stacks  # trial copy removed
        assert "mtio-staging_mtio-postgres-data" not in fake.volumes
        async with session_scope() as session:
            resource = await session.scalar(
                select(TenantResource).where(TenantResource.external_id == "mtio")
            )
            deployment = await session.scalar(
                select(Deployment).where(Deployment.project == "mtio")
            )
        assert resource is not None and resource.tenant_id == tenant_id
        assert deployment is not None and deployment.builder == "import"

        await _act(importer, tenant_id, run_id, "rollback")
        back = await _run(run_id)
        async with session_scope() as session:
            gone = await session.scalar(
                select(TenantResource).where(TenantResource.external_id == "mtio")
            )
        await close_db()
        return back, gone

    back, gone = asyncio.run(main())
    assert back.state == IMPORT_ROLLED_BACK, back.log
    assert UUID in fake.running and "mtio" not in fake.running
    assert gone is None
    # Volumes were copied cold during cutover: the source stack was stopped first.
    stop_at = fake.calls.index(["compose", "-p", UUID, "stop"])
    copy_at = max(
        i for i, c in enumerate(fake.calls)
        if c[:2] == ["volume", "create"] and c[2] == "mtio_mtio-postgres-data"
    )
    assert stop_at < copy_at


def test_failed_cutover_restores_coolify(actions_on):
    fake = FakeHost()
    fake.fail_up.add("mtio")
    importer = _importer(fake)

    async def main():
        tenant_id = await _tenant_id()
        run_id = await _plan(importer, tenant_id)
        await _act(importer, tenant_id, run_id, "stage")
        await _act(importer, tenant_id, run_id, "cutover")
        run = await _run(run_id)
        await close_db()
        return run

    run = asyncio.run(main())
    assert run.state == IMPORT_FAILED
    assert "rolled back to Coolify" in run.error
    assert UUID in fake.running and "mtio" not in fake.running


def test_cutover_refuses_when_source_not_serving(actions_on):
    fake = FakeHost()
    importer = _importer(fake)

    async def main():
        tenant_id = await _tenant_id()
        run_id = await _plan(importer, tenant_id)
        await _act(importer, tenant_id, run_id, "stage")
        fake.running.discard(UUID)
        await _act(importer, tenant_id, run_id, "cutover")
        run = await _run(run_id)
        await close_db()
        return run

    run = asyncio.run(main())
    assert run.state == IMPORT_FAILED
    assert "not serving HTTP" in run.error
    assert ["compose", "-p", UUID, "stop"] not in fake.calls


def test_actions_need_provider_actions_and_valid_state(monkeypatch):
    fake = FakeHost()
    importer = _importer(fake)

    async def main():
        tenant_id = await _tenant_id()
        run_id = await _plan(importer, tenant_id)
        errors = []
        monkeypatch.setattr(get_settings(), "enable_provider_actions", False)
        try:
            await _act(importer, tenant_id, run_id, "stage")
        except ImporterError as exc:
            errors.append(exc.status_code)
        monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
        for action in ("cutover", "rollback"):
            try:
                await _act(importer, tenant_id, run_id, action)
            except ImporterError as exc:
                errors.append(exc.status_code)
        await close_db()
        return errors

    assert asyncio.run(main()) == [403, 409, 409]


def test_api_is_platform_admin_only(client: TestClient):
    anonymous = client.get("/api/v1/importers/runs")
    assert anonymous.status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "supersecurepassword"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    listed = client.get("/api/v1/importers/runs", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []
    bad = client.post(
        "/api/v1/importers/coolify", headers=headers, json={"app_uuid": "NOT A UUID", "project": "x"}
    )
    assert bad.status_code == 422
