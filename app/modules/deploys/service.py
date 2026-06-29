"""Deploys — build a git repo into an image and run it as a Tetra app (the Vercel loop).

A self-contained plugin tool: clone+build via app/services/builder.py, run the resulting image
through the Tetra Engine with edge routing, and record it in the same tenant app inventory the
marketplace uses (so start/stop/remove/logs work uniformly). Build = Dockerfile (precedence) or
Nixpacks (zero-config). Write actions gated by ENABLE_PROVIDER_ACTIONS.
"""

import yaml
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services.builder import Builder
from app.services.docker_engine import DockerEngine, DockerEngineError, sanitize_project_name
from app.services.edge import apply_edge


def compose_for_image(image: str, port: int) -> str:
    """Minimal one-service compose wrapping a built image; edge labels are applied separately.

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

    async def deploy_git_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        git_url: str,
        ref: str = "main",
        name: str,
        port: int = 3000,
    ) -> dict:
        self._require_actions()
        project = sanitize_project_name(name)

        build = await self.builder.build_from_git(git_url, ref, project=project)
        # The image's own EXPOSE wins (Vercel-style "we detected the port"); else the request.
        port = build.port or port

        compose = compose_for_image(build.image, port)
        compose = apply_edge(compose, project=project, port=str(port))
        await self.engine.deploy_stack(project, compose, {})

        # Upsert into the shared app inventory so it lists/controls like a marketplace app.
        existing = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == (tenant_id or ""),
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == project,
            )
        )
        if existing is None:
            session.add(
                TenantResource(
                    tenant_id=tenant_id or "",
                    provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP,
                    external_id=project,
                    display_name=name,
                )
            )

        return {
            "ok": True,
            "project": project,
            "image": build.image,
            "builder": build.builder,
            "commit": build.commit,
            "port": port,
            "domain": f"{project}.{self.base_domain}" if self.base_domain else "",
        }
