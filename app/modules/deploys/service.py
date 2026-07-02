"""Deploys — build a git repo into an image and run it as a Tetra app (the Vercel loop).

Builds run **asynchronously**: the request creates a queued Deployment row and returns its id
immediately, while a background task clones+builds (Dockerfile precedence, else Nixpacks), runs the
image through the Tetra Engine with edge routing, and records it in the shared tenant app inventory.
The Deployment row carries the live status + a step log the console polls. Gated by
ENABLE_PROVIDER_ACTIONS.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from secrets import token_hex

import yaml
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session_scope
from app.models.deployment import (
    STATUS_BUILDING,
    STATUS_ERROR,
    STATUS_QUEUED,
    STATUS_READY,
    Deployment,
)
from app.models import AppEnvVar, DeployHook, PreviewEnv, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services.builder import BuildError, Builder
from app.services.docker_engine import DockerEngine, DockerEngineError, sanitize_project_name
from app.services.edge import apply_edge
from app.services.limits import apply_resource_limits
from app.services.quota import Allocation, QuotaService
from app.services.secrets import decrypt, encrypt


_TERMINAL_STATES = {STATUS_READY, STATUS_ERROR}

# fetch() -> (status, log_text) for the deployment, or None if it is gone/inaccessible.
DeploymentFetch = Callable[[], Awaitable[tuple[str, str] | None]]


def _sse_event(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_deploy_log_events(
    fetch: DeploymentFetch,
    request: Request,
    *,
    poll_interval: float = 1.0,
    max_seconds: float = 900.0,
) -> AsyncIterator[str]:
    """Poll a native deployment via ``fetch`` and emit incremental SSE events.

    Mirrors the Coolify streamer (``app.api.routes._stream_deployment_logs``): the
    Deployment row carries a growing newline-joined log, so each poll diffs by line
    count and emits new lines + status transitions, terminating on a terminal status,
    client disconnect, or the safety timeout. ``fetch`` returns ``(status, log)`` or
    ``None`` when the deployment is missing/not owned by the caller.
    """
    sent_lines = 0
    last_status: str | None = None
    elapsed = 0.0
    while True:
        if await request.is_disconnected():
            return
        current = await fetch()
        if current is None:
            yield _sse_event("error", {"message": "Deployment not found."})
            return
        status_value, log_text = current
        if status_value != last_status:
            last_status = status_value
            yield _sse_event("status", {"status": status_value})
        lines = log_text.split("\n") if log_text else []
        if len(lines) > sent_lines:
            for line in lines[sent_lines:]:
                yield _sse_event("log", line)
            sent_lines = len(lines)
        if status_value in _TERMINAL_STATES:
            yield _sse_event("done", {"status": status_value})
            return
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        if elapsed >= max_seconds:
            yield _sse_event("done", {"status": status_value, "timeout": True})
            return


def preview_project_name(project: str, branch: str) -> str:
    """Vercel-style preview stack name: ``blog`` + ``feat/login`` → ``blog-git-feat-login``."""
    return sanitize_project_name(f"{project}-git-{branch}")


def compose_for_image(image: str, port: int, env: dict[str, str] | None = None) -> str:
    """Minimal one-service compose wrapping a built image; edge labels applied separately.

    PORT is injected so Nixpacks-built apps (which listen on $PORT) bind the routed port.
    ``env`` (already-decrypted tenant vars) is layered on top; a user-supplied PORT is
    ignored so it can't override the router-assigned port.
    """
    environment = [f"PORT={port}"]
    for key, value in (env or {}).items():
        if key == "PORT":
            continue
        environment.append(f"{key}={value}")
    return yaml.safe_dump(
        {
            "services": {
                "app": {
                    "image": image,
                    "restart": "unless-stopped",
                    "environment": environment,
                    "expose": [str(port)],
                }
            }
        },
        sort_keys=False,
    )


class DeploysService:
    def __init__(self, request: Request) -> None:
        self.request = request
        settings = get_settings()
        self.engine = DockerEngine(docker_bin=settings.docker_bin)
        self.builder = Builder(docker_bin=settings.docker_bin, nixpacks_bin=settings.nixpacks_bin)
        self.base_domain = settings.apps_base_domain
        self.actions_enabled = settings.enable_provider_actions

    def _require_actions(self) -> None:
        if not self.actions_enabled:
            raise DockerEngineError(
                message="Provider actions are disabled (ENABLE_PROVIDER_ACTIONS=false).", code=403
            )

    async def start_deploy_for_tenant(
        self, tenant_id: str | None, *, git_url: str, ref: str, name: str, port: int
    ) -> str:
        """Create + commit a queued Deployment, kick off the background build, return its id.

        Atomically reserves a quota slot BEFORE the background task is scheduled.
        QuotaExceeded propagates to the caller (→ 402 handler); no task is created.
        """
        self._require_actions()
        project = sanitize_project_name(name)
        settings = get_settings()
        allocation = Allocation(
            cpu_millicores=settings.default_app_cpu_millicores,
            mem_mb=settings.default_app_mem_mb,
            disk_mb=settings.default_app_disk_mb,
        )
        async with session_scope() as session:
            # Reject if a TenantResource with this project name already exists for the tenant.
            existing = await session.scalar(
                select(TenantResource).where(
                    TenantResource.tenant_id == (tenant_id or ""),
                    TenantResource.provider == PROVIDER_DOCKER,
                    TenantResource.resource_type == RESOURCE_TYPE_APP,
                    TenantResource.external_id == project,
                )
            )
            if existing is not None:
                raise DockerEngineError(message=f"App '{project}' is already deployed.", code=409)

            # Atomically check quota and reserve BEFORE the build is scheduled.
            # QuotaExceeded is not caught here — it rolls back and propagates.
            quota = QuotaService(session, tenant_id or "")
            await quota.check_and_reserve(project, allocation, name)

            deployment = Deployment(
                tenant_id=tenant_id or "", project=project, git_url=git_url, ref=ref,
                status=STATUS_QUEUED, port=port,
            )
            session.add(deployment)
            await session.flush()
            deployment_id = deployment.id
        asyncio.create_task(
            self._run_deploy(deployment_id, tenant_id, git_url=git_url, ref=ref, project=project, port=port)
        )
        return deployment_id

    async def _set(self, deployment_id: str, log: list[str], *, status: str | None = None, **fields) -> None:
        async with session_scope() as session:
            deployment = await session.get(Deployment, deployment_id)
            if deployment is None:
                return
            if status:
                deployment.status = status
            for key, value in fields.items():
                setattr(deployment, key, value)
            deployment.log = "\n".join(log)

    async def _run_deploy(
        self, deployment_id: str, tenant_id: str | None, *, git_url: str, ref: str, project: str,
        port: int, env_project: str | None = None,
    ) -> None:
        """``env_project`` lets preview stacks inherit the PARENT app's env vars while
        building/running under their own project name (stack, subdomain, limits)."""
        log: list[str] = []
        try:
            log.append(f"→ cloning {git_url} @ {ref}")
            await self._set(deployment_id, log, status=STATUS_BUILDING)

            build = await self.builder.build_from_git(git_url, ref, project=project)
            effective_port = build.port or port
            log.append(f"✓ built {build.image} via {build.builder}")
            log.append(f"→ starting container on port {effective_port}")
            await self._set(deployment_id, log)

            env = await self.env_map_for_deploy(tenant_id, env_project or project)
            if env:
                log.append(f"→ injecting {len(env)} environment variable(s)")
                await self._set(deployment_id, log)
            extra_hosts = await self._custom_hosts(tenant_id, project)
            cpu, mem = await self._limits_for(tenant_id, project)
            compose = compose_for_image(build.image, effective_port, env)
            compose = apply_edge(
                compose, project=project, port=str(effective_port), extra_hosts=extra_hosts
            )
            compose = apply_resource_limits(compose, cpu_millicores=cpu, mem_mb=mem)
            await self.engine.deploy_stack(project, compose, {})

            # Reservation made in start_deploy_for_tenant stays on success.
            domain = f"{project}.{self.base_domain}" if self.base_domain else ""
            log.append(f"✓ live at https://{domain}" if domain else "✓ running")
            await self._set(
                deployment_id, log, status=STATUS_READY,
                image=build.image, builder=build.builder, commit=build.commit,
                port=effective_port, domain=domain,
            )
        except (BuildError, DockerEngineError) as exc:
            log.append(f"✗ {exc}")
            await self._set(deployment_id, log, status=STATUS_ERROR, error=str(exc)[:500])
            # Release the pre-build reservation so no orphan slot is left.
            # _run_deploy runs after the request session is closed, so open a fresh scope.
            async with session_scope() as release_session:
                await QuotaService(release_session, tenant_id or "").release(project)
        except Exception as exc:  # never leave a deployment stuck in "building"
            log.append(f"✗ unexpected: {exc}")
            await self._set(deployment_id, log, status=STATUS_ERROR, error=str(exc)[:500])
            async with session_scope() as release_session:
                await QuotaService(release_session, tenant_id or "").release(project)

    def stream_logs(
        self,
        tenant_id: str | None,
        deployment_id: str,
        request: Request,
        *,
        poll_interval: float = 1.0,
        max_seconds: float = 900.0,
    ) -> AsyncIterator[str]:
        """SSE build-log stream for a native deployment, scoped to ``tenant_id``.

        Each poll opens a fresh session (the request session is not safe to hold
        across the long-lived generator); returns None → the stream emits ``error``.
        """

        async def fetch() -> tuple[str, str] | None:
            async with session_scope() as session:
                deployment = await self.get_deployment_for_tenant(session, tenant_id, deployment_id)
                if deployment is None:
                    return None
                return deployment.status, deployment.log

        return stream_deploy_log_events(
            fetch, request, poll_interval=poll_interval, max_seconds=max_seconds
        )

    # ── Environment variables (tenant-scoped, encrypted at rest) ───────────
    async def set_env_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        project: str,
        *,
        key: str,
        value: str,
        is_secret: bool = False,
        is_build_time: bool = False,
    ) -> None:
        """Upsert an env var for (tenant, project, key); the value is encrypted at rest."""
        existing = await session.scalar(
            select(AppEnvVar).where(
                AppEnvVar.tenant_id == (tenant_id or ""),
                AppEnvVar.project == project,
                AppEnvVar.key == key,
            )
        )
        ciphertext = encrypt(value)
        if existing is not None:
            existing.value = ciphertext
            existing.is_secret = is_secret
            existing.is_build_time = is_build_time
        else:
            session.add(
                AppEnvVar(
                    tenant_id=tenant_id or "", project=project, key=key,
                    value=ciphertext, is_secret=is_secret, is_build_time=is_build_time,
                )
            )

    async def list_env_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str
    ) -> list[AppEnvVar]:
        rows = await session.scalars(
            select(AppEnvVar)
            .where(AppEnvVar.tenant_id == (tenant_id or ""), AppEnvVar.project == project)
            .order_by(AppEnvVar.key)
        )
        return list(rows.all())

    async def delete_env_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str, key: str
    ) -> bool:
        existing = await session.scalar(
            select(AppEnvVar).where(
                AppEnvVar.tenant_id == (tenant_id or ""),
                AppEnvVar.project == project,
                AppEnvVar.key == key,
            )
        )
        if existing is None:
            return False
        await session.delete(existing)
        return True

    async def _limits_for(self, tenant_id: str | None, project: str) -> tuple[int, int]:
        """(cpu_millicores, mem_mb) hard caps from the app's reservation row, falling back
        to config defaults (own session — runs post-request in the background task)."""
        settings = get_settings()
        async with session_scope() as session:
            row = await session.scalar(
                select(TenantResource).where(
                    TenantResource.tenant_id == (tenant_id or ""),
                    TenantResource.provider == PROVIDER_DOCKER,
                    TenantResource.resource_type == RESOURCE_TYPE_APP,
                    TenantResource.external_id == project,
                )
            )
        cpu = (row.cpu_millicores if row and row.cpu_millicores else 0) or settings.default_app_cpu_millicores
        mem = (row.mem_mb if row and row.mem_mb else 0) or settings.default_app_mem_mb
        return cpu, mem

    async def _custom_hosts(self, tenant_id: str | None, project: str) -> list[str]:
        """Verified custom domains to route alongside the auto subdomain (own session —
        runs post-request). Imported lazily to avoid a deploys↔domains import cycle."""
        from app.modules.domains.service import DomainsService

        async with session_scope() as session:
            return await DomainsService().verified_hostnames_for_project(
                session, tenant_id, project
            )

    async def env_map_for_deploy(self, tenant_id: str | None, project: str) -> dict[str, str]:
        """Decrypted {key: value} for injection at deploy time (own session — runs post-request)."""
        async with session_scope() as session:
            rows = await session.scalars(
                select(AppEnvVar).where(
                    AppEnvVar.tenant_id == (tenant_id or ""), AppEnvVar.project == project
                )
            )
            return {row.key: decrypt(row.value) for row in rows.all()}

    async def redeploy_for_tenant(
        self, tenant_id: str | None, *, git_url: str, ref: str, project: str, port: int
    ) -> str:
        """Rebuild + redeploy an EXISTING app (webhook/manual redeploy).

        Unlike ``start_deploy_for_tenant`` this does NOT reserve a quota slot (the app
        already holds one) and requires the app to exist — a redeploy of a project with
        no reservation would bypass quota, so a missing app raises 404.
        """
        self._require_actions()
        async with session_scope() as session:
            existing = await session.scalar(
                select(TenantResource).where(
                    TenantResource.tenant_id == (tenant_id or ""),
                    TenantResource.provider == PROVIDER_DOCKER,
                    TenantResource.resource_type == RESOURCE_TYPE_APP,
                    TenantResource.external_id == project,
                )
            )
            if existing is None:
                raise DockerEngineError(
                    message=f"App '{project}' is not deployed; deploy it first.", code=404
                )
            deployment = Deployment(
                tenant_id=tenant_id or "", project=project, git_url=git_url, ref=ref,
                status=STATUS_QUEUED, port=port,
            )
            session.add(deployment)
            await session.flush()
            deployment_id = deployment.id
        asyncio.create_task(
            self._run_deploy(deployment_id, tenant_id, git_url=git_url, ref=ref, project=project, port=port)
        )
        return deployment_id

    async def rollback_for_tenant(self, tenant_id: str | None, deployment_id: str) -> str:
        """Instant rollback: redeploy a PRIOR successful deployment's image, no rebuild.

        Creates a new Deployment pinned to the old image and re-runs the stack with
        current env. Requires the target to be a ``ready`` deployment with a built image
        and the app to still exist (no quota re-reservation). Caveat: the image must still
        be present locally (registry push + retention is a later hardening step).
        """
        self._require_actions()
        async with session_scope() as session:
            target = await session.get(Deployment, deployment_id)
            if target is None or target.tenant_id != (tenant_id or ""):
                raise DockerEngineError(message="Deployment not found.", code=404)
            if target.status != STATUS_READY or not target.image:
                raise DockerEngineError(
                    message="Can only roll back to a successful deployment with a built image.",
                    code=409,
                )
            existing = await session.scalar(
                select(TenantResource).where(
                    TenantResource.tenant_id == (tenant_id or ""),
                    TenantResource.provider == PROVIDER_DOCKER,
                    TenantResource.resource_type == RESOURCE_TYPE_APP,
                    TenantResource.external_id == target.project,
                )
            )
            if existing is None:
                raise DockerEngineError(
                    message=f"App '{target.project}' is not deployed; deploy it first.", code=404
                )
            new_deployment = Deployment(
                tenant_id=tenant_id or "", project=target.project, git_url=target.git_url,
                ref=target.ref, status=STATUS_QUEUED, port=target.port,
                image=target.image, commit=target.commit, builder=target.builder,
            )
            session.add(new_deployment)
            await session.flush()
            new_id = new_deployment.id
            project, image, port = target.project, target.image, target.port
        asyncio.create_task(
            self._run_rollback(new_id, tenant_id, project=project, image=image, port=port)
        )
        return new_id

    async def _run_rollback(
        self, deployment_id: str, tenant_id: str | None, *, project: str, image: str, port: int
    ) -> None:
        log: list[str] = []
        try:
            log.append(f"→ rolling back to {image}")
            await self._set(deployment_id, log, status=STATUS_BUILDING)
            env = await self.env_map_for_deploy(tenant_id, project)
            extra_hosts = await self._custom_hosts(tenant_id, project)
            cpu, mem = await self._limits_for(tenant_id, project)
            compose = compose_for_image(image, port, env)
            compose = apply_edge(compose, project=project, port=str(port), extra_hosts=extra_hosts)
            compose = apply_resource_limits(compose, cpu_millicores=cpu, mem_mb=mem)
            await self.engine.deploy_stack(project, compose, {})
            domain = f"{project}.{self.base_domain}" if self.base_domain else ""
            log.append("✓ rolled back" + (f" — live at https://{domain}" if domain else ""))
            await self._set(
                deployment_id, log, status=STATUS_READY, image=image, port=port, domain=domain
            )
        except (BuildError, DockerEngineError) as exc:
            log.append(f"✗ {exc}")
            await self._set(deployment_id, log, status=STATUS_ERROR, error=str(exc)[:500])
        except Exception as exc:  # never leave a deployment stuck in "building"
            log.append(f"✗ unexpected: {exc}")
            await self._set(deployment_id, log, status=STATUS_ERROR, error=str(exc)[:500])

    # ── Preview environments (per-branch ephemeral stacks) ─────────────────
    async def deploy_preview_for_tenant(
        self, tenant_id: str | None, *, git_url: str, branch: str, project: str, port: int
    ) -> tuple[str, str]:
        """Deploy (or refresh) the preview environment for ``branch`` of ``project``.

        Previews are separate Tetra Engine stacks named ``{project}-git-{branch}`` on
        their own subdomain, inheriting the parent app's env vars. They bypass app
        quota but are capped by ``max_previews_per_project`` and run with default
        resource limits. Returns ``(deployment_id, preview_domain)``.
        """
        self._require_actions()
        stack = preview_project_name(project, branch)
        domain = f"{stack}.{self.base_domain}" if self.base_domain else ""
        settings = get_settings()
        async with session_scope() as session:
            preview = await session.scalar(
                select(PreviewEnv).where(
                    PreviewEnv.tenant_id == (tenant_id or ""),
                    PreviewEnv.project == project,
                    PreviewEnv.branch == branch,
                )
            )
            if preview is None:
                count = await session.scalar(
                    select(func.count())
                    .select_from(PreviewEnv)
                    .where(
                        PreviewEnv.tenant_id == (tenant_id or ""),
                        PreviewEnv.project == project,
                    )
                )
                if (count or 0) >= settings.max_previews_per_project:
                    raise DockerEngineError(
                        message=(
                            f"Preview limit ({settings.max_previews_per_project}) reached for "
                            f"'{project}' — delete a preview or its branch first."
                        ),
                        code=409,
                    )
                preview = PreviewEnv(
                    tenant_id=tenant_id or "", project=project, branch=branch,
                    preview_project=stack, domain=domain,
                )
                session.add(preview)
            deployment = Deployment(
                tenant_id=tenant_id or "", project=stack, git_url=git_url, ref=branch,
                status=STATUS_QUEUED, port=port,
            )
            session.add(deployment)
            await session.flush()
            preview.last_deployment_id = deployment.id
            deployment_id = deployment.id
        asyncio.create_task(
            self._run_deploy(
                deployment_id, tenant_id, git_url=git_url, ref=branch, project=stack,
                port=port, env_project=project,
            )
        )
        return deployment_id, domain

    async def _remove_preview(self, preview_project: str) -> None:
        """Best-effort stack removal — the stack may already be gone."""
        try:
            await self.engine.remove_stack(preview_project, volumes=True)
        except DockerEngineError:
            pass

    async def teardown_preview_for_branch(
        self, tenant_id: str | None, project: str, branch: str
    ) -> bool:
        """Tear down the preview for ``branch`` (webhook branch-delete path)."""
        self._require_actions()
        async with session_scope() as session:
            preview = await session.scalar(
                select(PreviewEnv).where(
                    PreviewEnv.tenant_id == (tenant_id or ""),
                    PreviewEnv.project == project,
                    PreviewEnv.branch == branch,
                )
            )
            if preview is None:
                return False
            stack = preview.preview_project
            await session.delete(preview)
        await self._remove_preview(stack)
        return True

    async def delete_preview_for_tenant(self, tenant_id: str | None, preview_id: str) -> bool:
        """Tear down a preview by id (console/CLI delete path), tenant-scoped."""
        self._require_actions()
        async with session_scope() as session:
            preview = await session.get(PreviewEnv, preview_id)
            if preview is None or preview.tenant_id != (tenant_id or ""):
                return False
            stack = preview.preview_project
            await session.delete(preview)
        await self._remove_preview(stack)
        return True

    async def list_previews_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str | None = None
    ) -> list[PreviewEnv]:
        query = select(PreviewEnv).where(PreviewEnv.tenant_id == (tenant_id or ""))
        if project:
            query = query.where(PreviewEnv.project == project)
        rows = await session.scalars(query.order_by(PreviewEnv.created_at.desc()))
        return list(rows.all())

    # ── GitHub push-to-deploy hooks (secret encrypted at rest) ─────────────
    async def create_hook_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        project: str,
        *,
        git_url: str,
        ref: str = "main",
        port: int = 3000,
        previews: bool = True,
    ) -> tuple[DeployHook, str]:
        """Create a webhook for a project; returns (hook, raw_secret). The raw secret is
        shown to the owner once (to paste into GitHub) and stored only as ciphertext."""
        raw_secret = token_hex(20)
        hook = DeployHook(
            tenant_id=tenant_id or "", project=project, git_url=git_url, ref=ref, port=port,
            secret=encrypt(raw_secret), enabled=True, previews=previews,
        )
        session.add(hook)
        await session.flush()
        return hook, raw_secret

    async def list_hooks_for_tenant(
        self, session: AsyncSession, tenant_id: str | None
    ) -> list[DeployHook]:
        rows = await session.scalars(
            select(DeployHook)
            .where(DeployHook.tenant_id == (tenant_id or ""))
            .order_by(DeployHook.created_at.desc())
        )
        return list(rows.all())

    async def get_hook(self, session: AsyncSession, hook_id: str) -> DeployHook | None:
        """Load a hook by id — NOT tenant-scoped (the webhook receiver is unauthenticated
        and authenticates via HMAC, not a session)."""
        return await session.get(DeployHook, hook_id)

    async def delete_hook_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, hook_id: str
    ) -> bool:
        hook = await session.get(DeployHook, hook_id)
        if hook is None or hook.tenant_id != (tenant_id or ""):
            return False
        await session.delete(hook)
        return True

    async def get_deployment_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, deployment_id: str
    ) -> Deployment | None:
        deployment = await session.get(Deployment, deployment_id)
        if deployment is not None and deployment.tenant_id == (tenant_id or ""):
            return deployment
        return None

    async def list_deployments_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, limit: int = 20
    ) -> list[Deployment]:
        rows = await session.scalars(
            select(Deployment)
            .where(Deployment.tenant_id == (tenant_id or ""))
            .order_by(Deployment.created_at.desc())
            .limit(limit)
        )
        return list(rows.all())
