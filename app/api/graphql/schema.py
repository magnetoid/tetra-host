"""GraphQL query layer over the /api/v1 services.

Auth + tenancy: the whole surface requires the same signed API bearer token as REST
(minted at POST /api/v1/auth/login). The context getter resolves the admin *optionally*
so the GraphiQL IDE can load without a token; every resolver then calls `require_admin`,
so unauthenticated queries fail. Tenant isolation comes from passing `admin.tenant_id`
to the same `*_for_tenant` service methods the REST handlers use.
"""

from __future__ import annotations

from typing import Any

import strawberry
from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter

from app.api import contracts
from app.api.graphql import types
from app.api.security import read_api_token
from app.db.session import get_db_session
from app.models import AdminUser
from app.modules.auth.service import AuthService
from app.modules.dns.service import DnsService
from app.modules.mail.service import MailService
from app.modules.projects.service import ProjectsService
from app.services.http import ProviderAPIError


# ── Auth context ──────────────────────────────────────────────────────────
async def _optional_admin(request: Request, session: AsyncSession) -> AdminUser | None:
    authorization = request.headers.get("authorization") or ""
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    settings = request.state.settings
    payload = read_api_token(settings, token, max_age_seconds=settings.session_max_age_seconds)
    admin_id = payload.get("admin_user_id") if payload else None
    if not admin_id:
        return None
    admin = await AuthService(session).get_admin_by_id(admin_id)
    if admin is None or not admin.is_active:
        return None
    return admin


async def get_context(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {
        "request": request,
        "session": session,
        "admin": await _optional_admin(request, session),
    }


def require_admin(info: strawberry.Info) -> AdminUser:
    admin = info.context.get("admin")
    if admin is None:
        raise Exception("Authentication required. Provide an `Authorization: Bearer <token>` header.")
    return admin


def _provider(name: str, configured: bool, detail: str) -> types.Provider:
    return types.Provider(name=name, status="connected" if configured else "not_configured", detail=detail)


# ── Query ─────────────────────────────────────────────────────────────────
@strawberry.type
class Query:
    @strawberry.field(description="Provider health + tenant metrics for the overview.")
    async def dashboard(self, info: strawberry.Info) -> types.Dashboard:
        admin = require_admin(info)
        request = info.context["request"]
        session = info.context["session"]
        projects_service = ProjectsService(request)
        mail_service = MailService(request)
        dns_service = DnsService(request)

        providers: list[types.Provider] = []
        sites: list[Any] = []
        domains: list[Any] = []
        zones: list[Any] = []

        try:
            sites = await projects_service.list_sites_for_tenant(session, admin.tenant_id)
            configured = projects_service.client.is_configured()
            providers.append(
                _provider("Coolify", configured, f"{len(sites)} applications" if configured else "Credentials missing")
            )
        except ProviderAPIError as exc:
            providers.append(types.Provider(name="Coolify", status="degraded", detail=str(exc)))

        try:
            domains, _mailboxes = await mail_service.load_for_tenant(session, admin.tenant_id)
            configured = mail_service.client.is_configured()
            providers.append(
                _provider("Mailcow", configured, f"{len(domains)} domains" if configured else "Credentials missing")
            )
        except ProviderAPIError as exc:
            providers.append(types.Provider(name="Mailcow", status="degraded", detail=str(exc)))

        try:
            zones, _records, _selected = await dns_service.load_for_tenant(session, admin.tenant_id)
            configured = dns_service.client.is_configured()
            providers.append(
                _provider("Cloudflare", configured, f"{len(zones)} DNS zones" if configured else "Token missing")
            )
        except ProviderAPIError as exc:
            providers.append(types.Provider(name="Cloudflare", status="degraded", detail=str(exc)))

        admin_count = await session.scalar(
            select(func.count()).select_from(AdminUser).where(AdminUser.tenant_id == admin.tenant_id)
        ) or 0
        unhealthy = sum(1 for site in sites if "unhealthy" in site.status or "exited" in site.status)

        return types.Dashboard(
            providers=providers,
            metrics=types.DashboardMetrics(
                projects=len(sites),
                unhealthy_projects=unhealthy,
                mail_domains=len(domains),
                dns_zones=len(zones),
                admins=int(admin_count),
            ),
        )

    @strawberry.field(description="Coolify applications in the current tenant.")
    async def projects(self, info: strawberry.Info) -> list[types.Project]:
        admin = require_admin(info)
        service = ProjectsService(info.context["request"])
        sites = await service.list_sites_for_tenant(info.context["session"], admin.tenant_id)
        return [types.Project(**contracts.ProjectSummary(**s.model_dump()).model_dump()) for s in sites]

    @strawberry.field(description="Deployments for a project.")
    async def deployments(self, info: strawberry.Info, application_id: str) -> list[types.Deployment]:
        admin = require_admin(info)
        service = ProjectsService(info.context["request"])
        try:
            rows = await service.list_deployments_for_tenant(
                info.context["session"], admin.tenant_id, application_id
            )
        except ProviderAPIError as exc:
            raise Exception(str(exc)) from exc
        return [types.Deployment(**contracts.ProjectDeploymentSummary(**d.model_dump()).model_dump()) for d in rows]

    @strawberry.field(description="DNS zones + records for the current tenant.")
    async def dns(self, info: strawberry.Info) -> types.Dns:
        admin = require_admin(info)
        service = DnsService(info.context["request"])
        zones, records, selected = await service.load_for_tenant(info.context["session"], admin.tenant_id)
        return types.Dns(
            selected_zone=selected or "",
            zones=[types.DnsZone(**contracts.DNSZoneSummary(**z.model_dump()).model_dump()) for z in zones],
            records=[types.DnsRecord(**contracts.DNSRecordSummary(**r.model_dump()).model_dump()) for r in records],
        )

    @strawberry.field(description="Mail domains + mailboxes for the current tenant.")
    async def mail(self, info: strawberry.Info) -> types.Mail:
        admin = require_admin(info)
        service = MailService(info.context["request"])
        domains, mailboxes = await service.load_for_tenant(info.context["session"], admin.tenant_id)
        return types.Mail(
            domains=[types.MailDomain(**contracts.MailDomainSummary(**d.model_dump()).model_dump()) for d in domains],
            mailboxes=[types.Mailbox(**contracts.MailboxSummary(**m.model_dump()).model_dump()) for m in mailboxes],
        )


schema = strawberry.Schema(query=Query)


def build_graphql_router() -> GraphQLRouter:
    """The mountable /graphql router (GraphiQL IDE enabled; queries still require a token)."""
    return GraphQLRouter(schema, context_getter=get_context, graphql_ide="graphiql")
