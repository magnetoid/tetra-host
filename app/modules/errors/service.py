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
from app.services.build_diagnostics import Diagnosis
from app.services.error_diagnostics import analyze_error, anthropic_error_diagnoser
from app.services.glitchtip import GlitchtipClient

# Sentinel: distinguish "use the default AI diagnoser" from an explicit None (heuristic-only).
_UNSET = object()


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

    async def diagnose_error_for_project(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
        issue_id: str,
        *,
        diagnoser: object = _UNSET,
    ) -> tuple[dict[str, Any], Diagnosis] | None:
        """Explain one captured runtime error (heuristic + optional AI enrichment).

        Tenant-isolated through ``get_errors_for_project``. Returns ``(issue, diagnosis)``
        for the matching issue, or ``None`` when error tracking isn't ready or no issue with
        ``issue_id`` is in the project's recent issues. The offline heuristic always runs;
        AI enrichment is best-effort (any failure falls back to it). Pass ``diagnoser=None``
        to force heuristic-only (used in tests)."""
        data = await self.get_errors_for_project(session, tenant_id, application_id)
        if not data.get("ready"):
            return None
        issue = next(
            (i for i in data.get("issues", []) if str(i.get("id")) == str(issue_id)), None
        )
        if issue is None:
            return None

        title = str(issue.get("title") or "")
        culprit = str(issue.get("culprit") or "")
        level = str(issue.get("level") or "error")
        heuristic = analyze_error(title, culprit, level)

        fn = anthropic_error_diagnoser if diagnoser is _UNSET else diagnoser
        if fn is None:
            return issue, heuristic
        try:
            ai = await fn(title, culprit, level)
        except Exception:  # AI enrichment is best-effort — never fail the endpoint
            return issue, heuristic
        return issue, (ai or heuristic)
