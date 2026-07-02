---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T19:52:51'
updated: '2026-07-02T19:52:51'
rules:
- id: tetra-no-plesk-443-surgery
  description: Never rebind, share, or SNI-passthrough :443/:80 on the shared Plesk
    box's primary IP; custom-domain TLS terminates at Cloudflare (stage 1) or on a
    dedicated IP owned by Caddy (stage 2).
  severity: warn
---

# ADR 0009: Custom-domain TLS: Cloudflare for SaaS now, dedicated-IP Caddy On-Demand later

## Context
Custom domains (ADR-0007 domains plugin) are code-complete with the Caddy ask endpoint live, but prod TLS termination is blocked: the shared Plesk box has ONE public IPv4, Plesk nginx binds :443 on it for ~30 client sites, and its nginx lacks the stream module — so Caddy cannot share :443 and SNI passthrough would require unsafe surgery. tetra-caddy currently listens only on 127.0.0.1:8090 behind the nginx wildcard for *.apps.cloud-industry.com. User signed off on a two-stage path (2026-07-02).

## Decision
Stage 1 (now): terminate customer-domain TLS at Cloudflare using Cloudflare for SaaS custom hostnames on the cloud-industry.com zone. CF auto-issues/renews certs per custom hostname; traffic reaches the box on a CF-reachable path (public high port to Caddy or equivalent verified against current CF docs), where caddy-docker-proxy routes by Host via the existing tetra labels; access to that path is restricted to Cloudflare IP ranges. The domains plugin drives the CF custom-hostname lifecycle via the API (create on verify, delete on removal). Stage 2 (with Phase-3 Hetzner work): order a dedicated IPv4, bind Caddy 80/443 to it with on_demand_tls + the live /api/v1/edge/ask endpoint — the pure self-hosted pattern — and migrate domains off CF-for-SaaS or keep both as tiers. Never modify Plesk's :443 bindings or rebuild its nginx.

## Consequences
Positive: ships custom-domain HTTPS with zero risk to Plesk tenants; leverages the existing Cloudflare integration; stage 2 keeps the sovereign path. Trade-offs: stage-1 coupling to CF (free tier ~100 custom hostnames; per-hostname fees beyond), CF sees customer traffic, and the prod CLOUDFLARE_API_TOKEN must be re-minted with the SSL-and-Certificates:Edit scope (current token lacks it). Ops prerequisites: expose Caddy on a public port firewalled to CF ranges + CF fallback-origin/origin-rule config — verify exact mechanics against live CF docs before building (charter rule).
