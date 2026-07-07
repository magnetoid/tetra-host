"""Strawberry types for the GraphQL surface.

Field-for-field mirrors of the Pydantic contracts in `app.api.contracts`, so the GraphQL
and REST surfaces stay in lockstep. Resolvers build these from the same service models
the REST handlers return (via `_from`, which splats a contract model's `model_dump()`).
"""

from __future__ import annotations

import strawberry


@strawberry.type(description="A third-party provider's connection health.")
class Provider:
    name: str
    status: str
    detail: str


@strawberry.type(description="Aggregate counts across the current tenant.")
class DashboardMetrics:
    projects: int
    unhealthy_projects: int
    mail_domains: int
    dns_zones: int
    admins: int


@strawberry.type(description="Provider health + metrics for the operator overview.")
class Dashboard:
    providers: list[Provider]
    metrics: DashboardMetrics


@strawberry.type(description="A Coolify application in the current tenant.")
class Project:
    id: str
    name: str
    status: str
    primary_domain: str
    repository: str
    environment: str
    updated_at: str
    healthcheck_enabled: bool


@strawberry.type(description="A deployment of a project.")
class Deployment:
    id: str
    status: str
    created_at: str
    updated_at: str
    commit: str
    branch: str


@strawberry.type(description="A Cloudflare DNS zone.")
class DnsZone:
    id: str
    name: str
    status: str
    account_name: str
    paused: bool


@strawberry.type(description="A DNS record within a zone.")
class DnsRecord:
    id: str
    type: str
    name: str
    content: str
    ttl: int
    proxied: bool | None = None
    priority: int | None = None


@strawberry.type(description="A mail domain on the configured Mailcow instance.")
class MailDomain:
    domain_name: str
    mailboxes: int
    aliases: int
    quota_bytes: int
    active: bool


@strawberry.type(description="A mailbox on the configured Mailcow instance.")
class Mailbox:
    username: str
    name: str
    domain: str
    quota_bytes: int
    messages: int
    active: bool


@strawberry.type(description="DNS zones + records for the current tenant.")
class Dns:
    selected_zone: str
    zones: list[DnsZone]
    records: list[DnsRecord]


@strawberry.type(description="Mail domains + mailboxes for the current tenant.")
class Mail:
    domains: list[MailDomain]
    mailboxes: list[Mailbox]
