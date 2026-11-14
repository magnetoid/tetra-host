"""Shared checks for the paths that create a service (git deploy, template install, database).

Both raise ``DockerEngineError`` so each creation path surfaces them like its other errors:
the environment a new service goes into must belong to the tenant (404), and the stack name
must be free on the host across all tenants (409, ADR 0019).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Environment
from app.modules.workspaces.service import WorkspaceError, WorkspaceService
from app.services.docker_engine import DockerEngineError
from app.services.stack_names import stack_owner


async def placement_environment(
    session: AsyncSession, tenant_id: str | None, environment_id: str | None
) -> Environment | None:
    if not environment_id:
        return None
    try:
        return await WorkspaceService(session).require_environment(tenant_id, environment_id)
    except WorkspaceError as exc:
        raise DockerEngineError(message=exc.message, code=exc.status_code) from exc


async def ensure_stack_name_free(
    session: AsyncSession, tenant_id: str | None, project: str, *, verb: str
) -> None:
    owner = await stack_owner(session, project)
    if owner is None:
        return
    if owner == (tenant_id or ""):
        raise DockerEngineError(message=f"App '{project}' is already {verb}.", code=409)
    # Don't say who has it: tenants must not learn about each other.
    raise DockerEngineError(
        message=f"The name '{project}' is taken. Choose another name.", code=409
    )
