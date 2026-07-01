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

import yaml
from fastapi import Request
from sqlalchemy import select
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
from app.models import TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services.builder import BuildError, Builder
from app.services.docker_engine import DockerEngine, DockerEngineError, sanitize_project_name
from app.services.edge import apply_edge
from app.services.quota import Allocation, QuotaService


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


def compose_for_image(image: str, port: int) -> str:
    """Minimal one-service compose wrapping a built image; edge labels applied separately.

    PORT is injected so Nixpacks-built apps (which listen on $PORT) bind the routed port.
    """
    return yaml.safe_dump(
        {
            "services": {
                "app": {
                    "image": image,
                    "restart": "unless-stopped",
                    "environment": [f"PORT={port}"],
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
        self, deployment_id: str, tenant_id: str | None, *, git_url: str, ref: str, project: str, port: int
    ) -> None:
        log: list[str] = []
        try:
            log.append(f"→ cloning {git_url} @ {ref}")
            await self._set(deployment_id, log, status=STATUS_BUILDING)

            build = await self.builder.build_from_git(git_url, ref, project=project)
            effective_port = build.port or port
            log.append(f"✓ built {build.image} via {build.builder}")
            log.append(f"→ starting container on port {effective_port}")
            await self._set(deployment_id, log)

            compose = compose_for_image(build.image, effective_port)
            compose = apply_edge(compose, project=project, port=str(effective_port))
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
