"""Importing apps that Coolify serves only through its Traefik proxy (no host port)."""

import asyncio
import uuid

import pytest
import yaml
from sqlalchemy import select

from app.config import get_settings
from app.db.session import close_db, init_db, session_scope
from app.models import Deployment, ImportRun, Tenant
from app.models.import_run import IMPORT_LIVE, IMPORT_PLANNED, IMPORT_ROLLED_BACK, IMPORT_STAGED
from app.modules.importers.compose import ComposeImportError, build_stack, detect_routes
from app.modules.importers.service import STAGE_PORT_OFFSET, CoolifyImporter
from app.services.docker_engine import DockerEngine

RUUID = "e10k81izp11pberk24muhubm"
WEB = f"{RUUID}-20261111T040922"
ROUTED_SOURCE = f"""
services:
  {WEB}:
    image: '{RUUID}:8d1eea37'
    expose: ['3000']
    restart: unless-stopped
    networks:
      coolify:
        aliases: [{WEB}]
    labels:
      - traefik.enable=true
      - 'traefik.http.routers.http-0-{RUUID}.rule=Host(`morpheus.direct`) && PathPrefix(`/`)'
      - 'traefik.http.routers.https-1-{RUUID}.rule=Host(`www.morpheus.direct`) && PathPrefix(`/`)'
      - traefik.http.services.http-0-{RUUID}.loadbalancer.server.port=3000
      - traefik.http.services.https-1-{RUUID}.loadbalancer.server.port=3000
      - coolify.managed=true
networks:
  coolify:
    external: true
    name: coolify
"""
PROXY = "https://127.0.0.1:8445"


def test_detect_routes_reads_hosts_and_port():
    services = yaml.safe_load(ROUTED_SOURCE)["services"]
    [route] = detect_routes(services)
    assert route.service == WEB
    assert route.container_port == 3000
    assert route.hosts == ("morpheus.direct", "www.morpheus.direct")


def test_detect_routes_refuses_ambiguous_port():
    services = {
        "web": {
            "image": "x",
            "expose": ["3000", "4000"],
            "labels": {"traefik.http.routers.r.rule": "Host(`a.test`)"},
        }
    }
    with pytest.raises(ComposeImportError, match="ambiguous"):
        detect_routes(services)


def test_publish_adds_loopback_port_and_keeps_service_foreground():
    kwargs = dict(source_project=RUUID, source_dir=f"/data/coolify/applications/{RUUID}",
                  project="morpheus-direct", files_dir="/srv/stacks/morpheus-direct/files")
    _, unpublished = build_stack(ROUTED_SOURCE, "", **kwargs)
    assert unpublished.background == [WEB]  # without a port it looks like a worker

    text, plan = build_stack(ROUTED_SOURCE, "", **kwargs, publish={WEB: 9200}, port_offset=10000)
    svc = yaml.safe_load(text)["services"][WEB]
    assert svc["ports"] == ["127.0.0.1:19200:3000"]
    assert "labels" not in svc and "networks" not in svc
    assert plan.background == []
    assert [(p.service, p.host_port) for p in plan.ports] == [(WEB, 9200)]

    with pytest.raises(ComposeImportError, match="not routed"):
        build_stack(ROUTED_SOURCE, "", **kwargs, publish={"nope": 9200})


class RoutedHost:
    """Fake docker host + network for a single routed container."""

    def __init__(self) -> None:
        self.running = {RUUID}
        self.images = {f"{RUUID}:8d1eea37"}
        self.probes: list[tuple[int, str | None]] = []

    async def __call__(self, argv, stdin, env):
        args = argv[1:]
        if args[:2] == ["run", "--rm"] and "cat" in args:
            return (0, ROUTED_SOURCE, "") if args[-1].endswith("docker-compose.yaml") else (1, "", "")
        if args[:2] == ["image", "inspect"]:
            return (0, "sha256:x", "") if args[-1] in self.images else (1, "", "no such image")
        if args[0] == "tag":
            self.images.add(args[2])
            return 0, "", ""
        if args[:3] == ["port", "coolify-proxy", "443/tcp"]:
            return 0, "127.0.0.1:8445\n", ""
        if args[0] == "compose":
            project, verb = args[2], args[3]
            if verb in ("-f", "start"):
                self.running.add(project)
            elif verb in ("stop", "down"):
                self.running.discard(project)
            return 0, "", ""
        return 1, "", f"unexpected docker call {args}"

    async def probe(self, port: int, *, vhost: str | None = None) -> str:
        self.probes.append((port, vhost))
        if port == 9200 + STAGE_PORT_OFFSET:
            up = "morpheus-direct-staging" in self.running
        elif port == 9200:
            up = "morpheus-direct" in self.running
        else:
            return "closed"
        if not up:
            return "closed"
        # The app only answers its own hostname.
        return "http:200" if vhost == "morpheus.direct" else "http:400"

    async def upstream(self, url: str, vhost: str) -> str:
        assert url == PROXY
        return "http:200" if RUUID in self.running and vhost == "morpheus.direct" else "http:502"


async def _no_sleep(_: float) -> None:
    return None


def test_routed_app_plan_stage_cutover_rollback(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)
    fake = RoutedHost()
    importer = CoolifyImporter(
        engine=DockerEngine(runner=fake), probe=fake.probe, upstream_probe=fake.upstream,
        sleep=_no_sleep, stacks_dir="/srv/stacks", wait_seconds=0.05, poll_seconds=0,
    )

    async def act(tenant_id, run_id, action):
        async with session_scope() as session:
            await importer.request(session, tenant_id=tenant_id, actor="ops@example.com",
                                   run_id=run_id, action=action)
        await importer.execute(run_id, action)
        async with session_scope() as session:
            run = await session.get(ImportRun, run_id)
            return run.state, run.error, dict(run.summary), run.log

    async def main():
        await init_db()
        async with session_scope() as session:
            tenant = Tenant(name="P", slug=f"p-{uuid.uuid4().hex[:8]}", status="active")
            session.add(tenant)
            await session.flush()
            tenant_id = tenant.id
            run = await importer.plan(session, tenant_id=tenant_id, actor="ops@example.com",
                                      app_uuid=RUUID, project="morpheus-direct")
            run_id, planned = run.id, (run.state, dict(run.summary))
        staged = await act(tenant_id, run_id, "stage")
        live = await act(tenant_id, run_id, "cutover")
        running_after_cutover = set(fake.running)
        async with session_scope() as session:
            dep = await session.scalar(select(Deployment).where(Deployment.project == "morpheus-direct"))
            dep_view = (dep.domain, dep.port)
        rolled = await act(tenant_id, run_id, "rollback")
        await close_db()
        return planned, staged, live, running_after_cutover, dep_view, rolled

    planned, staged, live, running_after_cutover, dep_view, rolled = asyncio.run(main())

    state, summary = planned
    assert state == IMPORT_PLANNED
    assert summary["routes"] == [{"service": WEB, "container_port": 3000, "host_port": 9200,
                                  "hosts": ["morpheus.direct", "www.morpheus.direct"]}]
    assert summary["stage_exclude"] == []  # the web container is not a background worker
    assert summary["coolify_proxy"] == PROXY
    assert any("point nginx" in w for w in summary["warnings"])

    assert staged[0] == IMPORT_STAGED, staged[1]
    assert staged[2]["baseline"] == {"9200": "http:200"}  # read through Coolify's proxy
    assert staged[2]["stage_probe"] == {"9200": "http:200"}
    assert (9200 + STAGE_PORT_OFFSET, "morpheus.direct") in fake.probes

    assert live[0] == IMPORT_LIVE, live[1]
    assert (
        "ACTION NEEDED: point nginx for morpheus.direct, www.morpheus.direct at "
        "http://127.0.0.1:9200" in live[3]
    )
    assert RUUID not in running_after_cutover and "morpheus-direct" in running_after_cutover
    assert dep_view == ("morpheus.direct", 9200)

    assert rolled[0] == IMPORT_ROLLED_BACK, rolled[1]
    assert RUUID in fake.running and "morpheus-direct" not in fake.running
