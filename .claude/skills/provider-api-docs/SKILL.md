---
name: provider-api-docs
description: Use when implementing, modifying, or debugging Coolify or Cloudflare (or Mailcow) API integration — e.g. app/services/coolify.py, app/services/cloudflare.py, app/services/mailcow.py, deploy/DNS/mail features, or any /api/v1 provider endpoint. Fetches and combines the LATEST official upstream API docs into one reference so code matches current API truth instead of stale or remembered assumptions.
---

# Provider API Docs (Coolify + Cloudflare + Mailcow)

Tetra Host orchestrates third-party providers. Their APIs change, and this repo
has already been bitten by coding against stale shapes (a whole obsolete
integration-test file; confusion over whether Coolify supports rollback). **Before
writing or changing provider code, work from the current upstream docs — never from
memory.**

## When to use

- Adding or changing a method in `app/services/{coolify,cloudflare,mailcow}.py`.
- Building a feature on a provider capability (deploy, rollback, DNS CRUD, mailboxes).
- Debugging a provider call (wrong shape, 4xx/5xx, missing field).
- Any time you're about to assume "the API supports X" — verify X exists first.

## Procedure

1. **Fetch the latest docs** with WebFetch from the canonical sources below. Pull the
   specific operation page(s) you need (method, path, query params, JSON body, response
   envelope), not just the index.
2. **Verify the capability exists** before building UI/logic on it. If the docs don't
   document it, it probably isn't in the public API (see Coolify rollback below). Say so
   instead of shipping a fake affordance.
3. **Combine** the relevant endpoints into `docs/providers/combined-api-reference.md`
   (create/update it): one section per provider, a table of `METHOD path — purpose —
   key params/response`, plus any gotchas. Date the file and link the source URLs.
4. **Implement** against that reference, matching this repo's client conventions
   (below). Add/adjust tests.

## Canonical sources (always re-fetch — they change)

- **Coolify API reference:** https://coolify.io/docs/api-reference/api/ and the
  per-operation pages under `.../api-reference/api/operations/<name>` (e.g.
  `deploy-by-tag-or-uuid`, `list-deployments`). General docs: https://coolify.io/docs.
- **Cloudflare API:** https://developers.cloudflare.com/api/ — for this project mainly
  DNS: https://developers.cloudflare.com/api/resources/dns/ (zones + records).
- **Mailcow API:** https://mailcow.docs.apiary.io/ (domains, mailboxes, aliases).

## Repo client conventions (match these, don't reinvent)

- Provider clients take an injected `httpx.AsyncClient` + `TTLCache` and call through the
  shared retrying helper `request_json(...)` in `app/services/http.py`; they raise
  `ProviderAPIError`. Do **not** instantiate `httpx.AsyncClient()` inside a client.
- Construct via `from_settings(http_client=..., cache=...)`. Normalize raw payloads into
  the pydantic models in each service module (`CoolifyApplication`, `CloudflareDNSRecord`,
  `MailcowDomain`, …). Keep route handlers thin; logic lives in the service.

## Verified gotchas (re-confirm against live docs each time)

- **Coolify rollback is web-UI only and image-based** — "redeploys the exact image from
  that deployment without rebuilding." There is **no rollback API**, no image
  list/select API, and **no API to deploy a specific commit SHA** (commit-SHA rollback is
  Coolify bug coollabsio/coolify#1976). Don't build an API-backed rollback button.
- **Coolify build logs** are exposed only as a polled, growing `deployment_log` string
  (no native stream); diff by line to stream incrementally.
- **Cloudflare** wraps responses in `{ success, result, errors }`; read `result`.
- The official `coolify-cli` is a thin wrapper over the same REST API — it has no
  capability the API lacks.
