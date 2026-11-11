"""Coolify → Tetra Engine importer: plan, trial copy, cutover, rollback.

Flow for one Coolify compose application (roadmap phase 4):

1. **plan**: read the app's rendered compose + ``.env`` from Coolify's data dir, rewrite
   them (``compose.build_stack``), check images and volumes exist, record a run. Read-only.
2. **stage**: a trial copy next to the live app — project ``<project>-staging``, host
   ports shifted by ``STAGE_PORT_OFFSET``, background workers excluded, volumes copied
   hot. Passes when every port answers like the live one does.
3. **cutover**: stop the Coolify containers (``docker compose stop``, so they stay on
   disk), copy volumes cold, start ``<project>`` on the original ports. nginx already
   proxies those ports, so no proxy change is needed. Passes when every port answers as
   it did before the stop; otherwise the Coolify containers are started again.
4. **rollback** (during the soak): stop ``<project>``, start the Coolify containers.
   Writes made on the engine after cutover are not copied back.

Coolify's own start/stop API is deliberately not used: stopping through Coolify removes
the containers, which would turn a seconds-long rollback into a rebuild.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import _REPO_ROOT, session_scope
from app.models.audit import AuditEvent
from app.models.deployment import STATUS_READY, Deployment
from app.models.import_run import (
    IMPORT_BUSY_STATES,
    IMPORT_CUTTING_OVER,
    IMPORT_FAILED,
    IMPORT_LIVE,
    IMPORT_PLANNED,
    IMPORT_ROLLED_BACK,
    IMPORT_ROLLING_BACK,
    IMPORT_STAGED,
    IMPORT_STAGING,
    ImportRun,
)
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP, TenantResource
from app.modules.importers.compose import ComposeImportError, ImportPlan, build_stack
from app.modules.importers.host import HostOps, probe_port
from app.services.docker_engine import DockerEngine, DockerEngineError, sanitize_project_name
from app.services.http import ProviderAPIError
from app.services.secrets import decrypt, encrypt

logger = logging.getLogger(__name__)

STAGE_PORT_OFFSET = 10000
BUILDER_IMPORT = "import"
_UUID_RE = re.compile(r"^[a-z0-9]{6,64}$")

ACTION_STAGE = "stage"
ACTION_CUTOVER = "cutover"
ACTION_ROLLBACK = "rollback"
_ALLOWED_FROM = {
    ACTION_STAGE: {IMPORT_PLANNED, IMPORT_STAGED, IMPORT_FAILED, IMPORT_ROLLED_BACK},
    ACTION_CUTOVER: {IMPORT_STAGED, IMPORT_FAILED, IMPORT_ROLLED_BACK},
    ACTION_ROLLBACK: {IMPORT_LIVE},
}
_BUSY_STATE = {
    ACTION_STAGE: IMPORT_STAGING,
    ACTION_CUTOVER: IMPORT_CUTTING_OVER,
    ACTION_ROLLBACK: IMPORT_ROLLING_BACK,
}

Probe = Callable[[int], Awaitable[str]]
Sleep = Callable[[float], Awaitable[None]]
SessionFactory = Callable[[], Any]

# Background steps must outlive the request that started them (see deploys/service.py).
_background_tasks: set[asyncio.Task] = set()


def spawn_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class ImporterError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def default_stacks_dir() -> str:
    configured = get_settings().engine_stacks_dir.strip()
    return configured or str(Path(_REPO_ROOT) / "data" / "stacks")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _imported_tag(project: str, service: str, source_ref: str) -> str:
    tag = source_ref.rsplit(":", 1)[-1] if ":" in source_ref.split("/")[-1] else "latest"
    name = re.sub(r"[^a-z0-9._-]+", "-", f"{project}-{service}".lower()).strip("-.")
    clean_tag = re.sub(r"[^A-Za-z0-9_.-]+", "", tag)[:12] or "latest"
    return f"{name}:imported-{clean_tag}"


class CoolifyImporter:
    def __init__(
        self,
        *,
        engine: DockerEngine | None = None,
        coolify: Any = None,
        probe: Probe = probe_port,
        sleep: Sleep = asyncio.sleep,
        session_factory: SessionFactory = session_scope,
        stacks_dir: str | None = None,
        wait_seconds: float = 180.0,
        poll_seconds: float = 3.0,
    ) -> None:
        settings = get_settings()
        self.settings = settings
        self.engine = engine or DockerEngine()
        self.host = HostOps(self.engine, helper_image=settings.import_helper_image)
        self.coolify = coolify
        self.probe = probe
        self.sleep = sleep
        self.session_factory = session_factory
        self.stacks_dir = stacks_dir or default_stacks_dir()
        self.wait_seconds = wait_seconds
        self.poll_seconds = poll_seconds

    # ── queries ──────────────────────────────────────────────────────────────

    async def list_runs(self, session: AsyncSession, tenant_id: str) -> list[ImportRun]:
        rows = await session.scalars(
            select(ImportRun)
            .where(ImportRun.tenant_id == tenant_id)
            .order_by(ImportRun.created_at.desc())
        )
        return list(rows)

    async def get_run(self, session: AsyncSession, tenant_id: str, run_id: str) -> ImportRun:
        run = await session.get(ImportRun, run_id)
        if run is None or run.tenant_id != tenant_id:
            raise ImporterError("Import run not found.", 404)
        return run

    # ── plan ─────────────────────────────────────────────────────────────────

    def _source_dir(self, uuid: str) -> str:
        return f"{self.settings.coolify_data_dir.rstrip('/')}/applications/{uuid}"

    def _files_dir(self, project: str) -> str:
        return f"{self.stacks_dir.rstrip('/')}/{project}/files"

    def _build(
        self,
        run_like: dict[str, Any],
        compose_text: str,
        env_text: str,
        *,
        stage: bool,
    ) -> tuple[str, ImportPlan]:
        project = run_like["project"]
        return build_stack(
            compose_text,
            env_text,
            source_project=run_like["source_project"],
            source_dir=run_like["source_dir"],
            project=f"{project}-staging" if stage else project,
            files_dir=self._files_dir(project),
            port_offset=STAGE_PORT_OFFSET if stage else 0,
            exclude=sorted(
                set(run_like.get("skip", []))
                | (set(run_like.get("stage_exclude", [])) if stage else set())
            ),
            image_overrides=run_like.get("image_overrides") or {},
        )

    async def plan(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        actor: str,
        app_uuid: str,
        project: str,
        stage_exclude: list[str] | None = None,
    ) -> ImportRun:
        app_uuid = (app_uuid or "").strip().lower()
        if not _UUID_RE.match(app_uuid):
            raise ImporterError("That does not look like a Coolify application uuid.", 422)
        project = sanitize_project_name(project)
        if project == app_uuid:
            raise ImporterError("Choose a project name different from the Coolify uuid.", 422)
        await self._ensure_free(session, tenant_id, app_uuid, project)

        source_dir = self._source_dir(app_uuid)
        try:
            compose_text = await self.host.read_file(source_dir, "docker-compose.yaml")
            env_text = await self.host.read_file(source_dir, ".env", missing_ok=True)
        except DockerEngineError as exc:
            raise ImporterError(f"Could not read the Coolify app files: {exc.message}", 502) from exc

        base = {"project": project, "source_project": app_uuid, "source_dir": source_dir}
        try:
            _, first = self._build(base, compose_text, env_text, stage=False)
        except ComposeImportError as exc:
            raise ImporterError(str(exc), 422) from exc
        # A locally built image that is missing means Coolify never built or ran that
        # service. A background worker in that state is not part of the live app, so it
        # is left out of both stacks; anything else is a hard stop.
        skip: list[str] = []
        built: dict[str, str] = {}
        for svc, ref in first.locally_built.items():
            if await self.host.image_exists(ref):
                built[svc] = ref
            elif svc in first.background:
                skip.append(svc)
            else:
                raise ImporterError(f"Image {ref} for {svc} is not on this host.", 422)
        exclude = sorted(stage_exclude) if stage_exclude is not None else first.background
        exclude = [svc for svc in exclude if svc not in skip]
        overrides = {svc: _imported_tag(project, svc, ref) for svc, ref in built.items()}
        run_like = {
            **base, "skip": sorted(skip), "stage_exclude": exclude, "image_overrides": overrides,
        }
        try:
            _, prod = self._build(run_like, compose_text, env_text, stage=False)
            _, staged = self._build(run_like, compose_text, env_text, stage=True)
        except ComposeImportError as exc:
            raise ImporterError(str(exc), 422) from exc

        warnings = list(prod.warnings)
        for svc in skip:
            warnings.append(
                f"{svc}: never built or run by Coolify (no image on this host); left out of "
                "the import, as it is not part of the running app today"
            )
        for svc, ref in prod.images.items():
            if svc not in prod.locally_built and not await self.host.image_exists(ref):
                warnings.append(f"{svc}: image {ref} is not local and will be pulled")
        volumes: list[dict[str, Any]] = []
        stage_names = {v.key: v.target_name for v in staged.volumes}
        for vol in prod.volumes:
            size = await self.host.volume_size(vol.source_name)
            if size is None:
                raise ImporterError(f"Volume {vol.source_name} does not exist.", 422)
            volumes.append(
                {
                    "key": vol.key,
                    "source": vol.source_name,
                    "target": vol.target_name,
                    "stage_target": stage_names.get(vol.key, ""),
                    "size_bytes": size,
                }
            )

        coolify_info = await self._coolify_info(app_uuid)
        if coolify_info.get("auto_deploy"):
            warnings.append(
                "Coolify auto-deploy is on for this app; disable it before cutover so a git "
                "push does not start the old stack again."
            )
        elif coolify_info and coolify_info.get("auto_deploy") is None:
            warnings.append(
                "Could not confirm Coolify auto-deploy is off; check it in Coolify before "
                "cutover so a git push does not start the old stack again."
            )

        summary = {
            **run_like,
            "files_dir": self._files_dir(project),
            "stage_project": f"{project}-staging",
            "stage_port_offset": STAGE_PORT_OFFSET,
            "services": prod.services,
            "background": first.background,
            "locally_built": built,
            "ports": [
                {
                    "service": p.service,
                    "host_ip": p.host_ip,
                    "host_port": p.host_port,
                    "container_port": p.container_port,
                }
                for p in prod.ports
            ],
            "volumes": volumes,
            "binds": sorted({b.rel_path for b in prod.binds}),
            "warnings": warnings,
            "coolify": coolify_info,
        }
        run = ImportRun(
            tenant_id=tenant_id,
            source="coolify",
            source_ref=app_uuid,
            project=project,
            state=IMPORT_PLANNED,
            summary=summary,
            secret_blob=encrypt(json.dumps({"compose": compose_text, "env": env_text})),
            created_by=actor,
            log=f"[{_now()}] planned by {actor}\n",
        )
        session.add(run)
        session.add(
            AuditEvent(actor_email=actor, action="import.plan", target=project, details=app_uuid)
        )
        await session.flush()
        return run

    async def _ensure_free(
        self, session: AsyncSession, tenant_id: str, app_uuid: str, project: str
    ) -> None:
        taken = await session.scalar(
            select(TenantResource).where(
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == project,
            )
        )
        if taken is not None:
            raise ImporterError(f"An engine app named '{project}' already exists.", 409)
        active = await session.scalar(
            select(ImportRun).where(
                ImportRun.source_ref == app_uuid,
                ImportRun.state.in_(IMPORT_BUSY_STATES | {IMPORT_LIVE}),
            )
        )
        if active is not None:
            raise ImporterError(
                f"Import run {active.id} for this app is {active.state}.", 409
            )

    async def _coolify_info(self, app_uuid: str) -> dict[str, Any]:
        if self.coolify is None or not self.coolify.is_configured():
            return {}
        try:
            raw = await self.coolify.get_application_raw(app_uuid)
        except ProviderAPIError as exc:
            return {"error": str(exc)[:200]}
        # Coolify's OpenAPI documents is_auto_deploy_enabled only as a write field;
        # GET may return it top-level, under `settings`, or not at all (None = unknown).
        settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
        auto = raw.get("is_auto_deploy_enabled", settings.get("is_auto_deploy_enabled"))
        return {
            "name": raw.get("name", ""),
            "fqdn": raw.get("fqdn", ""),
            "status": raw.get("status", ""),
            "auto_deploy": None if auto is None else bool(auto),
        }

    # ── actions ──────────────────────────────────────────────────────────────

    async def request(
        self, session: AsyncSession, *, tenant_id: str, actor: str, run_id: str, action: str
    ) -> ImportRun:
        """Validate and claim the run for ``action``; the caller then runs ``execute``."""
        if action not in _ALLOWED_FROM:
            raise ImporterError(f"Unknown action '{action}'.", 400)
        if not self.settings.enable_provider_actions:
            raise ImporterError("Provider actions are disabled (ENABLE_PROVIDER_ACTIONS).", 403)
        run = await self.get_run(session, tenant_id, run_id)
        if run.state not in _ALLOWED_FROM[action]:
            raise ImporterError(f"Cannot {action} a run that is {run.state}.", 409)
        run.state = _BUSY_STATE[action]
        run.error = ""
        run.log += f"[{_now()}] {action} requested by {actor}\n"
        session.add(
            AuditEvent(actor_email=actor, action=f"import.{action}", target=run.project, details=run.id)
        )
        await session.flush()
        return run

    async def execute(self, run_id: str, action: str) -> None:
        async with self.session_factory() as session:
            run = await session.get(ImportRun, run_id)
            if run is None:
                return
            step = {
                ACTION_STAGE: self._stage,
                ACTION_CUTOVER: self._cutover,
                ACTION_ROLLBACK: self._rollback,
            }[action]
            try:
                await step(session, run)
            except Exception as exc:  # noqa: BLE001 — every failure must land on the run
                message = getattr(exc, "message", None) or str(exc) or type(exc).__name__
                logger.exception("import %s %s failed", action, run_id)
                run.state = IMPORT_FAILED
                run.error = message[:1000]
                await self._log(session, run, f"FAILED: {message}")

    async def _log(self, session: AsyncSession, run: ImportRun, message: str) -> None:
        run.log += f"[{_now()}] {message}\n"
        await session.commit()

    def _secrets(self, run: ImportRun) -> tuple[str, str]:
        data = json.loads(decrypt(run.secret_blob))
        return data["compose"], data["env"]

    def _probe_ports(self, run: ImportRun) -> list[int]:
        return sorted({int(p["host_port"]) for p in run.summary.get("ports", [])})

    async def _snapshot(self, ports: list[int], offset: int = 0) -> dict[str, str]:
        return {str(port): await self.probe(port + offset) for port in ports}

    async def _wait_for(
        self, ports: list[int], expected: dict[str, str], *, offset: int = 0
    ) -> dict[str, str]:
        """Poll until each port answers like ``expected`` (ports expected closed are skipped)."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.wait_seconds
        current: dict[str, str] = {}
        while True:
            current = await self._snapshot(ports, offset)
            if all(
                current.get(port) == want
                for port, want in expected.items()
                if want != "closed"
            ):
                return current
            if loop.time() >= deadline:
                diff = {
                    p: f"{expected[p]} → {current.get(p)}"
                    for p in expected
                    if expected[p] != "closed" and current.get(p) != expected[p]
                }
                raise ImporterError(f"Ports did not come up as expected: {diff}", 504)
            await self.sleep(self.poll_seconds)

    async def _wait_closed(self, ports: list[int]) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.wait_seconds
        while True:
            snap = await self._snapshot(ports)
            if all(v == "closed" for v in snap.values()):
                return
            if loop.time() >= deadline:
                raise ImporterError(f"Source ports are still open after stop: {snap}", 504)
            await self.sleep(self.poll_seconds)

    async def _prepare(self, session: AsyncSession, run: ImportRun) -> None:
        """Tag images under engine-owned names and copy bind-mounted files."""
        summary = run.summary
        for svc, ref in (summary.get("locally_built") or {}).items():
            target = summary["image_overrides"][svc]
            await self.host.tag_image(ref, target)
            await self._log(session, run, f"image {svc}: {ref} → {target}")
        binds = summary.get("binds") or []
        if binds:
            await self.host.copy_files(summary["source_dir"], binds, summary["files_dir"])
            await self._log(session, run, f"copied files: {', '.join(binds)}")

    async def _stage(self, session: AsyncSession, run: ImportRun) -> None:
        summary = dict(run.summary)
        compose_text, env_text = self._secrets(run)
        stage_yaml, _ = self._build(summary, compose_text, env_text, stage=True)
        ports = self._probe_ports(run)
        await self._prepare(session, run)
        try:
            await self.engine.remove_stack(summary["stage_project"])
        except DockerEngineError:
            pass
        for vol in summary["volumes"]:
            await self._log(session, run, f"copying {vol['source']} → {vol['stage_target']} (live copy)")
            await self.host.copy_volume(vol["source"], vol["stage_target"])
        await self._log(session, run, f"starting {summary['stage_project']}")
        await self.engine.deploy_stack(summary["stage_project"], stage_yaml)
        baseline = await self._snapshot(ports)
        await self._log(session, run, f"live answers: {baseline}")
        result = await self._wait_for(ports, baseline, offset=STAGE_PORT_OFFSET)
        summary["baseline"] = baseline
        summary["stage_probe"] = result
        run.summary = summary
        run.state = IMPORT_STAGED
        await self._log(
            session, run,
            f"trial copy matches live on ports +{STAGE_PORT_OFFSET}: {result}",
        )

    async def _cutover(self, session: AsyncSession, run: ImportRun) -> None:
        summary = dict(run.summary)
        compose_text, env_text = self._secrets(run)
        prod_yaml, _ = self._build(summary, compose_text, env_text, stage=False)
        ports = self._probe_ports(run)
        baseline = await self._snapshot(ports)
        if not any(v.startswith("http:") for v in baseline.values()):
            raise ImporterError(f"The Coolify app is not serving HTTP right now: {baseline}", 409)
        await self._log(session, run, f"live answers before cutover: {baseline}")
        await self._prepare(session, run)

        source = summary["source_project"]
        stopped = False
        try:
            await self._log(session, run, f"stopping Coolify containers ({source})")
            await self.engine.stop_stack(source)
            stopped = True
            await self._wait_closed(ports)
            for vol in summary["volumes"]:
                await self._log(session, run, f"copying {vol['source']} → {vol['target']}")
                await self.host.copy_volume(vol["source"], vol["target"])
            await self._log(session, run, f"starting {run.project} on the original ports")
            await self.engine.deploy_stack(run.project, prod_yaml)
            result = await self._wait_for(ports, baseline)
        except Exception as exc:
            if stopped:
                await self._log(session, run, f"cutover failed ({exc}); restoring Coolify")
                await self._restore_source(session, run)
                raise ImporterError(f"{getattr(exc, 'message', exc)} — rolled back to Coolify") from exc
            raise

        await self._register(session, run)
        summary["baseline"] = baseline
        summary["cutover_probe"] = result
        run.summary = summary
        run.state = IMPORT_LIVE
        await self._log(session, run, f"LIVE on the engine: {result}")
        await self._teardown_stage(session, run)

    async def _restore_source(self, session: AsyncSession, run: ImportRun) -> None:
        try:
            await self.engine.stop_stack(run.project)
        except DockerEngineError:
            pass
        await self.engine.start_stack(run.summary["source_project"])
        baseline = run.summary.get("baseline") or {}
        if baseline:
            await self._wait_for(self._probe_ports(run), baseline)
        await self._log(session, run, "Coolify containers are serving again")

    async def _rollback(self, session: AsyncSession, run: ImportRun) -> None:
        await self._log(
            session, run,
            "rolling back: changes written on the engine since cutover are NOT copied back",
        )
        await self._restore_source(session, run)
        await session.execute(
            delete(TenantResource).where(
                TenantResource.tenant_id == run.tenant_id,
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == run.project,
            )
        )
        await session.execute(
            delete(Deployment).where(
                Deployment.tenant_id == run.tenant_id,
                Deployment.project == run.project,
                Deployment.builder == BUILDER_IMPORT,
            )
        )
        run.state = IMPORT_ROLLED_BACK
        await self._log(session, run, f"rolled back; {run.project} is stopped, Coolify serves")

    async def _register(self, session: AsyncSession, run: ImportRun) -> None:
        exists = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == run.tenant_id,
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == run.project,
            )
        )
        if exists is None:
            session.add(
                TenantResource(
                    tenant_id=run.tenant_id,
                    provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP,
                    external_id=run.project,
                    display_name=f"{run.project} (imported from Coolify)",
                )
            )
        fqdn = (run.summary.get("coolify") or {}).get("fqdn", "") or ""
        domain = fqdn.split(",")[0].removeprefix("https://").removeprefix("http://").strip("/")
        session.add(
            Deployment(
                tenant_id=run.tenant_id,
                project=run.project,
                status=STATUS_READY,
                builder=BUILDER_IMPORT,
                image=f"coolify:{run.source_ref}"[:255],
                domain=domain[:255],
                port=0,
                log=f"→ imported from Coolify app {run.source_ref} (run {run.id})\n✓ running",
            )
        )
        await session.flush()

    async def _teardown_stage(self, session: AsyncSession, run: ImportRun) -> None:
        try:
            await self.engine.remove_stack(run.summary["stage_project"])
            for vol in run.summary["volumes"]:
                if vol.get("stage_target"):
                    await self.host.remove_volume(vol["stage_target"])
            await self._log(session, run, "removed the trial copy")
        except DockerEngineError as exc:
            await self._log(session, run, f"could not remove the trial copy: {exc.message}")
