---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-03T09:00:00'
updated: '2026-07-03T09:00:00'
rules:
- id: tetra-mail-envelope-is-truth
  rule: Mailcow write calls must inspect the response envelope — an HTTP 200 carrying
    type danger/error is a FAILED operation and must raise ProviderAPIError; never
    treat a 200 as success by status code alone.
- id: tetra-mail-ownership-404
  rule: Tenant ownership checks on mail objects (domains, mailboxes, aliases) deny
    with 404 — never 403 — so the API does not leak which mail objects exist on the
    platform; ownership is TenantResource rows, fail-closed.
- id: tetra-mail-password-custody
  rule: Mailbox/relayhost passwords are accepted only via JSON body over TLS or
    interactive getpass — never argv flags, never logs, and mailbox creation is never
    exposed as an MCP tool (a password in tool args would enter the model transcript).
---

# ADR 0015: Mail writes — Mailcow + ESP relay + DNS automation, shipped dormant

## Context
Phase 2 of the program (ADR 0004): per-tenant mailboxes with deliverable outbound. The
platform decision (charter + shared-box constraint) is a **dedicated Mailcow host** —
Plesk's Postfix/Dovecot own all mail ports on the shared box — plus a **per-domain ESP
relay** for outbound reputation. The dedicated host does not exist yet; waiting for it
would serialize hardware procurement in front of software. The Hetzner/AI pattern
(ADR 0011/0013) applies: build the full write path against the verified API, test it
network-free, ship it dormant behind config.

## Decision
Working from mailcow's shipped `openapi.yaml` (recorded in
`docs/providers/combined-api-reference.md`, per the provider-api-docs rule):

1. **MailcowClient writes** — create/delete domain, mailbox, alias; DKIM get/generate;
   relayhost create/list/assign (`edit/domain attr.relayhost`). All through the shared
   retrying `request_json`; the mailcow envelope (`[{type: success|danger|error}]`) is
   the source of truth — a 200 "danger" raises `ProviderAPIError` (rule
   `tetra-mail-envelope-is-truth`). Unconfigured: reads stay `[]`, writes raise 503.
2. **Tenant-scoped orchestration** in `MailService`: creating a domain runs the whole
   platform flow — mailcow domain → immediate `TenantResource` registration (scoping
   applies from the first read) → DKIM generation → optional default ESP relayhost
   assignment (`MAIL_DEFAULT_RELAYHOST_ID`) → **best-effort DNS automation**: MX (to
   `MAIL_HOSTNAME`), SPF (`MAIL_SPF_RECORD`), DKIM TXT, DMARC (`MAIL_DMARC_RECORD`)
   created in the tenant's longest-suffix-matching Cloudflare zone via the existing
   tenant-gated `DnsService`, returning a per-record created/failed/skipped report
   instead of ever failing the domain create. Aliases are scoped by domain ownership
   (`filter_aliases`); deletions unregister resources; DNS records are intentionally
   left in place on domain deletion (shared-zone safety).
3. **Three surfaces**: `/api/v1/mail/*` endpoints (relayhost creation is
   platform-admin only — ESP credentials are a platform secret), `tetra mail
   domain|mailbox|alias|dkim|relayhost` CLI verbs (passwords via getpass only), and
   MCP read tools + double-gated write tools — with **mailbox creation deliberately
   absent from MCP** (rule `tetra-mail-password-custody`).

## Consequences
When the dedicated Mailcow host lands, activation is config only: set `MAILCOW_URL`,
`MAILCOW_API_KEY`, `MAIL_HOSTNAME`, mint an ESP relayhost with `tetra mail relayhost
add`, and set `MAIL_DEFAULT_RELAYHOST_ID`. Until then prod behavior is unchanged
(reads empty, writes 503). The DKIM/SPF/DMARC automation is the platform's strongest
cross-provider synergy (Mailcow keys × Cloudflare DNS) and is what makes tenant mail
domains deliverable by default. Panel/console mail write UIs are deferred to the
activation slice — forms against a dormant backend would be dead UI; CLI+API+MCP carry
parity until then. Adversarially reviewed before merge (tenancy/security, correctness,
dormancy, parity — 22 agents, per-finding refutation): 9 distinct confirmed defects
fixed, notably (a) a **cross-tenant zone-enumeration oracle** — DNS automation matched
against unfiltered zones, so a foreign tenant's zone was observably different from "no
zone" (now: only tenant-accessible zones are candidates; foreign ≡ nonexistent); (b) an
**ownership-orphan wedge** — `request_json` leaked raw `httpx.ConnectTimeout`/bad-JSON
past best-effort catches, 500-ing after the provider create and rolling back the
ownership row (fixed at the root: `app/services/http.py` now converts ALL transport and
parse failures to `ProviderAPIError` — a platform-wide contract hardening — plus
`except Exception` on every post-create enrichment step); (c) cross-tenant stale rows on
delete, a blank-int env-var boot crash, and an MCP stdio-loop crash on bad-typed args.
Each fix carries a regression test.
