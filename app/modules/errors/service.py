"""Per-project error tracking, backed by a self-hosted GlitchTip instance.

Config-gated (like the analytics integration): with no ``GLITCHTIP_URL`` the Errors
tab shows a "connect error tracking" state. Each project maps to a GlitchTip project
(found or created on demand by a slug derived from the project), tenant-isolated via the
ProjectsService access guard. Returns the project DSN (to wire the SDK) plus recent issues.
"""

import re
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.service import ProjectsService
from app.services.glitchtip import GlitchtipClient


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "project"


def _issue(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id") or ""),
        "title": str(raw.get("title") or raw.get("metadata", {}).get("type") or "Error"),
        "culprit": str(raw.get("culprit") or ""),
        "level": str(raw.get("level") or "error"),
        "count": int(raw.get("count") or 0),
        "user_count": int(raw.get("userCount") or 0),
        "last_seen": str(raw.get("lastSeen") or ""),
        "status": str(raw.get("status") or "unresolved"),
        "permalink": str(raw.get("permalink") or ""),
    }


class ErrorsService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.glitchtip = GlitchtipClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )
        self.projects = ProjectsService(request)

    def is_configured(self) -> bool:
        return self.glitchtip.is_configured()

    async def get_errors_for_project(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
    ) -> dict[str, Any]:
        # Tenant isolation + project fetch in one guarded call (raises 403/404).
        app = await self.projects.get_site_for_tenant(session, tenant_id, application_id)

        if not self.glitchtip.is_configured():
            return {"configured": False, "ready": False}

        name = (getattr(app, "name", "") if app else "") or application_id
        slug = _slugify(name)

        project = await self.glitchtip.find_or_create_project(slug=slug, name=name)
        if project is None:
            return {
                "configured": True,
                "ready": False,
                "reason": "No GlitchTip team is available to create this project in.",
            }

        project_slug = str(project.get("slug") or slug)
        dsn = await self.glitchtip.get_project_dsn(project_slug)
        issues = await self.glitchtip.list_issues(project_slug)

        return {
            "configured": True,
            "ready": True,
            "project_slug": project_slug,
            "dsn": dsn,
            "issues": [_issue(i) for i in issues if isinstance(i, dict)],
        }
