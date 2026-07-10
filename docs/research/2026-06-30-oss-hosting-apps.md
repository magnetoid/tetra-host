# OSS apps to make Tetra a project + website hosting platform

> Knowledge-grounded synthesis (live multi-agent web research was rate-limited; verify stars/exact license revisions with a live pass before committing to any one tool). Builds on `typed-napping-stearns.md` (PaaS plumbing roadmap) and the Coolify feature research — does not repeat them.

## Integration model
Tetra is the **control plane + premium UX**; it already has its **own Docker engine** + a Coolify client + a Cloudflare DNS client. Three ways an OSS app slots in, all as a plugin module (`app/modules/<name>/` + service + `/api/v1` + `tetra` verb + console):
1. **One-click tenant service** — provisioned for a customer via the **own engine** (compose template) or via **Coolify** (`provision_*`), recorded as a `TenantResource`, reachable via Caddy edge. (CMS, analytics, search, db-admin go here.)
2. **Platform sidecar** — one shared instance Tetra runs for itself, wrapped behind a thin service (object storage, monitoring, git, registry). Tenant-scoped at the control-plane layer.
3. **Frontend-over-provider** — Tetra UI drives Coolify/Cloudflare APIs (the existing pattern); add the missing Coolify surfaces (app/static-site provisioning, projects/environments) rather than re-implementing.

## Prioritized "implement next" (value/effort)
| # | Tool | Bucket | License | V/E | One-line fit |
|---|------|--------|---------|-----|--------------|
| 1 | **Static-site hosting** (Caddy + own builder, Hugo/Astro/Eleventy) | Website | — | H/M | The core "website hosting" primitive: build SSG → serve via Caddy + wildcard TLS. Pairs with the roadmap's edge slice. |
| 2 | **Uptime Kuma** | Infra | MIT | H/S | Per-site/app uptime + status pages; embed via auth-proxied iframe or its API. Cheap, huge value. |
| 3 | **Umami** | Website | MIT | H/S | Privacy-first per-site web analytics; one-click + a snippet; MIT (clean). |
| 4 | **Gitea** (or **Forgejo**) | Infra | MIT | H/M | Internal git so users `git push` to Tetra (not just GitHub); feeds the own deploy engine + Gitea Actions for CI. |
| 5 | **Ghost** | Website | MIT | H/M | One-click blog/newsletter/membership site — the flagship "website" offering; proven Docker image. |
| 6 | **SeaweedFS** (or **Garage**) | Infra | Apache-2.0 (Garage AGPL) | M/M | S3 object storage for build artifacts, site assets, backups; SeaweedFS is Apache-2.0 + low-footprint. |
| 7 | **Coolify app + static-site provisioning** | Frontend | — | M/M | Close the Coolify gap: create apps/static sites via API (not just manage), so "frontend over Coolify" is complete. |
| 8 | **Meilisearch** | Infra | MIT | M/S | One-click search-as-a-service for hosted sites; MIT, fast, light. |
| 9 | **PayloadCMS** (or **Strapi**) | Website | MIT | M/M | Headless CMS one-click for app-backed sites; Payload is MIT + Next-native (fits the console stack). |
| 10 | **Woodpecker CI** | Infra | Apache-2.0 | M/M | Pipeline CI beyond git-push (tests/build steps) tied to Gitea; Apache-2.0. |

## A. Website hosting layer (the new emphasis)
- **Static hosting** — the highest-value primitive. Own builder runs the SSG (Hugo, Astro, Eleventy, Next `export`), output served by **Caddy** (roadmap edge slice) with wildcard + custom-domain TLS. A `staticsite` plugin: connect repo/upload → build → publish. Mirrors Netlify/Cloudflare Pages.
- **CMS / sites (one-click):** **Ghost** (MIT) blog/membership; **PayloadCMS** (MIT, Next-native) and **Strapi** (MIT core) headless; **WordPress** (proven on the box); **Outline** (BSL — wiki, run unmodified) ; **Directus** (BSL 1.1 — careful, hosting restrictions).
- **Site builders (low/no-code):** **GrapesJS** (BSD, embeddable editor — could power a Tetra "build a page" feature), **Webstudio** (AGPL — run unmodified), **Plasmic** (MIT-ish).
- **Analytics:** **Umami** (MIT, recommended), **Plausible** (AGPL — sidecar only), **Matomo** (GPL).
- **Supporting:** form backends (**Formbricks** AGPL, or a tiny custom endpoint), comments (**Remark42** MIT), status pages (Uptime Kuma covers this).

## B. Project/PaaS infra gaps (beyond the roadmap)
- **Object storage / S3:** **SeaweedFS** (Apache-2.0, low RAM) ✅, **Garage** (AGPL, tiny, S3), **MinIO** (AGPL + recently stripped console features — use cautiously). Powers assets, artifacts, backups (the roadmap's backup slice can target it).
- **Monitoring/uptime:** **Uptime Kuma** (MIT) ✅, **Gatus** (Apache-2.0, config-as-code).
- **Git hosting:** **Gitea** (MIT) / **Forgejo** (MIT/GPL fork) — internal push-to-deploy; complements the roadmap's GitHub App.
- **Email:** the box can't host SMTP (Plesk owns the ports — per project memory), so **API email** (Resend/Postmark) for transactional + **Listmonk** (AGPL, sidecar) for newsletters; not self-hosted MTA.
- **Search:** **Meilisearch** (MIT) ✅ / **Typesense** (GPL-3).
- **Db admin / queues / cache:** Adminer, pgweb (one-click admin UIs); Redis/KeyDB + queues already provisionable via the Coolify DB work.
- **Automation:** **n8n** (Sustainable-Use/"fair-code" — usage restrictions; run as an unmodified one-click for tenants, don't resell as managed n8n).

## C. How comparable OSS platforms compose (architecture cues)
- **Coolify / Dokploy / CapRover / Dokku / Easypanel** — all are Docker-compose orchestrators with a one-click "services" catalog + Traefik/Caddy/nginx edge + Let's Encrypt. Tetra's differentiator = multi-tenant control plane + frontend-over-Coolify + its own engine. **Don't fork Coolify** — compose it.
- **Cloudron** — strongest "app store" UX + per-app backups + email; good model for the **one-click catalog + per-app backup** experience (which the Coolify DB-backup work started).
- Net: Tetra's edge is the **tenant/plan/billing control plane + a curated app catalog spanning both website and project hosting**, not another raw orchestrator.

## License landmines (run AGPL/BSL/SSPL only as UNMODIFIED sidecars; never fork into Tetra's code; flag BSL/SSPL "can't offer as a competing managed service" clauses)
- **AGPL-3.0:** Plausible, Garage, MinIO, Listmonk, Webstudio, Formbricks, Uptime Kuma is **MIT** (safe). → fine to *run* unmodified + offer to tenants; don't link/modify into the control plane.
- **BSL 1.1:** Directus, Outline (+ historically Sentry) — usage restrictions; check the "hosting service" clause before offering as managed.
- **SSPL:** (none recommended here) — avoid.
- **GPL/AGPL clean alternatives preferred where possible:** Umami (MIT) over Plausible; SeaweedFS (Apache) over MinIO; Meilisearch (MIT) over Typesense; Gitea/Forgejo (MIT); Ghost/Payload/Strapi (MIT).

## Suggested sequencing (maps onto the existing roadmap)
1. Finish the roadmap **edge/TLS slice** (Caddy) — unblocks static hosting + custom domains + every one-click app's URL.
2. **Static-site hosting** plugin (builder + Caddy) — the headline "website hosting".
3. **Catalog v2**: curate the one-click set (Ghost, WordPress, Umami, Meilisearch, Uptime Kuma, db-admin) via the own engine, tenant-scoped + quota-gated.
4. **SeaweedFS** (platform S3) — assets/artifacts/backups.
5. **Gitea + Woodpecker** — internal push-to-deploy + CI.
6. **Coolify app/static-site provisioning** — complete the frontend-over-Coolify surface.
