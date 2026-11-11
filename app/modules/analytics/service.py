"""Per-project web analytics, backed by a self-hosted Umami instance.

Config-gated (like Cloudflare): with no ``UMAMI_URL`` the Metrics tab shows
a "connect analytics" state. Each project maps to an Umami *website* resolved by the
engine app's domain (found or created on demand). Tenant isolation is enforced by
``resolve_engine_app`` before any Umami call.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.engine_apps import resolve_engine_app
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


def _valid_domain(value: str) -> bool:
    """Reject empties and non-hostnames."""
    d = (value or "").strip().lower()
    return bool(d) and " " not in d and "." in d


class AnalyticsService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.umami = UmamiClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )

    def is_configured(self) -> bool:
        return self.umami.is_configured()

    async def get_analytics_for_project(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        project: str,
        *,
        period: str = "7d",
    ) -> dict[str, Any]:
        # Tenant isolation guard (raises EngineAppNotFound if the app isn't this tenant's).
        app = await resolve_engine_app(session, tenant_id, project)

        if not self.umami.is_configured():
            return {"configured": False, "ready": False, "period": period}

        domain = app.domain if _valid_domain(app.domain) else ""
        name = app.name
        if not domain:
            return {
                "configured": True,
                "ready": False,
                "period": period,
                "reason": "This app has no domain yet, so analytics can't be attached.",
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
