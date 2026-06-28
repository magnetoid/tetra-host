from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.mailcow import MailcowClient, MailcowDomain, MailcowMailbox
from app.services.tenant_resources import TenantResourceFilter


class MailService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = MailcowClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )

    async def load(self, refresh: bool = False) -> tuple[list[MailcowDomain], list[MailcowMailbox]]:
        domains = await self.client.list_domains(refresh=refresh)
        mailboxes = await self.client.list_mailboxes(refresh=refresh)
        return domains, mailboxes

    async def load_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        refresh: bool = False,
    ) -> tuple[list[MailcowDomain], list[MailcowMailbox]]:
        domains, mailboxes = await self.load(refresh=refresh)
        return await TenantResourceFilter(session, tenant_id).filter_mail(domains, mailboxes)
