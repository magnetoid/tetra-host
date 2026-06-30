"""Per-project web analytics, backed by a self-hosted Umami instance.

Config-gated (like Coolify/Cloudflare): with no ``UMAMI_URL`` the Metrics tab shows
a "connect analytics" state. Each project maps to an Umami *website* resolved by the
project's domain (found or created on demand). Tenant isolation is enforced via the
ProjectsService access guard before any Umami call.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.service import ProjectsService
from app.services.umami import UmamiClient

PERIOD_DAYS: dict[str, int] = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}


def _num(value: Any) -> int:
    if isinstance(value, dict):
        value = value.get("value", 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _summary(stats: dict[str, Any]) -> dict[str, int]:
    pageviews = _num(stats.get("pageviews"))
    visitors = _num(stats.get("visitors"))
    visits = _num(stats.get("visits")) or visitors
    bounces = _num(stats.get("bounces"))
    totaltime = _num(stats.get("totaltime"))
    return {
        "pageviews": pageviews,
        "visitors": visitors,
        "visits": visits,
        "bounce_rate": round((bounces / visits) * 100) if visits else 0,
        "avg_seconds": round(totaltime / visits) if visits else 0,
    }


def _series(pageviews: dict[str, Any]) -> list[dict[str, Any]]:
    pv = pageviews.get("pageviews", []) if isinstance(pageviews, dict) else []
    sessions = pageviews.get("sessions", []) if isinstance(pageviews, dict) else []
    sess_by_x = {str(p.get("x")): _num(p.get("y")) for p in sessions if isinstance(p, dict)}
    out: list[dict[str, Any]] = []
    for point in pv:
        if not isinstance(point, dict):
            continue
        x = str(point.get("x"))
        out.append({"date": x, "pageviews": _num(point.get("y")), "sessions": sess_by_x.get(x, 0)})
    return out


def _domain_of(fqdn: str) -> str:
    """First hostname from a Coolify fqdn (strip scheme/path, take first of a list)."""
    first = (fqdn or "").split(",")[0].strip()
    first = first.replace("https://", "").replace("http://", "")
    return first.split("/")[0].strip()


def _valid_domain(value: str) -> bool:
    """Reject empties, Coolify's "No domain" placeholder, and non-hostnames."""
    d = (value or "").strip().lower()
    return bool(d) and " " not in d and "." in d and d != "no domain"


class AnalyticsService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.umami = UmamiClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )
        self.projects = ProjectsService(request)

    def is_configured(self) -> bool:
        return self.umami.is_configured()

    async def get_analytics_for_project(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
        *,
        period: str = "7d",
    ) -> dict[str, Any]:
        # Tenant isolation guard (raises 403 if the project isn't this tenant's).
        await self.projects.ensure_access_for_tenant(session, tenant_id, application_id)

        if not self.umami.is_configured():
            return {"configured": False, "ready": False, "period": period}

        # Resolve domain + name from the application LIST: primary_domain is reliably
        # populated there, whereas the single-app GET omits fqdn on this Coolify version.
        # Coolify uses the literal "No domain" placeholder when a site isn't exposed.
        domain, name = "", application_id
        for app in await self.projects.list_sites():
            if app.id == application_id:
                candidate = _domain_of(app.primary_domain) or _domain_of(app.fqdn)
                domain = candidate if _valid_domain(candidate) else ""
                name = app.name or application_id
                break
        if not domain:
            return {
                "configured": True,
                "ready": False,
                "period": period,
                "reason": "This project has no domain yet, so analytics can't be attached.",
            }

        website = await self.umami.find_or_create_website(domain=domain, name=name)
        website_id = str(website.get("id") or website.get("websiteId") or "")
        if not website_id:
            return {
                "configured": True,
                "ready": False,
                "period": period,
                "reason": "Could not resolve the analytics website.",
            }

        days = PERIOD_DAYS.get(period, 7)
        now = datetime.now(UTC)
        end_ms = int(now.timestamp() * 1000)
        start_ms = int((now - timedelta(days=days)).timestamp() * 1000)
        unit = "hour" if days <= 1 else "day"

        stats = await self.umami.get_stats(website_id, start_ms, end_ms)
        pageviews = await self.umami.get_pageviews(website_id, start_ms, end_ms, unit=unit)
        top_pages = await self.umami.get_metrics(website_id, start_ms, end_ms, "url", limit=8)
        top_referrers = await self.umami.get_metrics(website_id, start_ms, end_ms, "referrer", limit=8)

        return {
            "configured": True,
            "ready": True,
            "period": period,
            "website_id": website_id,
            "tracking_snippet": self.umami.tracking_snippet(website_id),
            "summary": _summary(stats),
            "series": _series(pageviews),
            "top_pages": [
                {"label": str(m.get("x") or "(none)"), "count": _num(m.get("y"))} for m in top_pages
            ],
            "top_referrers": [
                {"label": str(m.get("x") or "(direct)"), "count": _num(m.get("y"))}
                for m in top_referrers
            ],
        }
