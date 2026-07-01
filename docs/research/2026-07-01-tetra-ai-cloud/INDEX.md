# Tetra AI Cloud — Platform Research (2026-07-01)

Deep web research + codebase analysis backing the **Tetra AI Cloud** evolution plan
(one open-source hosting panel fusing Plesk + Coolify + Cloudflare + Vercel-grade DX).
Twelve parallel research/exploration streams; each file below carries inline source URLs + access dates.
The synthesized, phased plan lives outside the repo at `~/.claude/plans/i-want-to-go-scalable-plum.md`.

## Locked strategic decisions
1. **Tenancy = trusted / own customers** — shared-kernel Docker + cgroup v2 hard limits + per-tenant networks + patched runc now; gVisor/microVM tier later (seam kept clean).
2. **First focus = multi-tenant SaaS foundation + Vercel-DX over Coolify.**
3. **Mail = dedicated Mailcow host + ESP relay for outbound.**
4. **AI = fast-follow** — Tetra MCP server over `/api/v1` (human-gated writes) + AI-assisted deploy/log debugging.

## Reports
| Topic | File | Headline finding |
|---|---|---|
| Coolify backend | *(inline below)* | v4.0 GA Apr 2026, Apache-2.0 (safe to white-label), `/api/v1` OpenAPI 3.1 — but **200 req/min**, **poll (no event bus)**, **team = tenancy boundary**, **TLS driven indirectly via FQDN**, no API deprecation policy. |
| Orchestration alternatives | [orchestration-alternatives.md](orchestration-alternatives.md) | Dokploy closest Coolify swap (license split risk); k3s strongest multi-tenancy (highest ops cost); **Nomad is BUSL — avoid for a paid host**. Stay Coolify + own engine. |
| Build layer | [build-layer.md](build-layer.md) | Nixpacks maintenance-mode → **Railpack** (Go/BuildKit, smaller images, still beta) → CNB in reserve. Tiered builder. |
| Reverse proxy / edge | [reverse-proxy-edge.md](reverse-proxy-edge.md) | **Caddy On-Demand TLS + `ask` endpoint** is the unique answer for customer custom domains; Traefik can't run multi-instance LE without Enterprise. |
| Hetzner / IaC | *(inline below)* | hcloud REST, **3,600 req/hr**, **per-project token = free per-tenant isolation**, hourly billing (great for previews), cheap egress. **OpenTofu (MPL) over Terraform (BSL)**; Pulumi Automation API best Python fit; direct API for hot-path. |
| Multi-tenancy / isolation | [multi-tenancy-isolation.md](multi-tenancy-isolation.md) | cgroup v2 hard caps (`--cpus`+`memory.max`+`pids.max`+`io.max`); shared kernel OK only for trusted tenants (patch runc ≥1.2.8/1.3.3); gVisor for untrusted. Billing: OpenMeter/Lago → Stripe meters. |
| Vercel-DX blocks | [vercel-dx.md](vercel-dx.md) | Coolify already ships most of the Vercel loop; real gaps = build-log SSE shim, rollback (registry-backed), custom-domain TLS at scale, multi-tenant secret custody. |
| PHP/WordPress/mail | [php-wordpress-mail.md](php-wordpress-mail.md) | Coolify runs WordPress but is **not** a shared-hosting substrate; **Hetzner blocks port 25/465 by default** → relay outbound via ESP. |
| AI-native / future trends | [ai-native-trends.md](ai-native-trends.md) | MCP donated to Linux Foundation (Dec 2025); **Code Mode** pattern; ship AI ops as "draft + approve"; **golden paths over knobs**; WASM/edge is narrow, not a container replacement. |
| Plesk migration | [plesk-migration.md](plesk-migration.md) | No turnkey tool; manifest→build→cutover state machine; **⚠ disable Plesk domain mail at cutover** (same-domain loopback), **⚠ disable registrar DNSSEC before NS change**; ~2–4h/site. |

---

## Coolify backend — key findings (no sidecar; captured here)
- **Version/API:** v4.0.0 GA **late April 2026**; v4.1 (2026-05-18) added Railpack, structured audit logging, instance-level read-only MCP. REST **`/api/v1`**, **OpenAPI 3.1**, Laravel Sanctum bearer tokens (`ID|SECRET`, shown once).
- **License:** **Apache-2.0** — commercial use + white-label/resell permitted (retain notices). Self-hosted fully free.
- **Coverage:** apps (5 create paths: public/private git, Dockerfile, Compose, image), lifecycle, env CRUD (bulk), FQDN + auto-TLS via Traefik ACME, 8 managed DB engines + S3 backups, services catalog (280+), server list/validate, deployments (trigger/cancel/list).
- **Constraints for a panel:** **team = tenancy boundary** (one team-scoped token per tenant; no sub-project RBAC — issue #6894 open); **no outbound event bus → poll** deployment/resource state; **200 req/min** default (429 + Retry-After); **SSL not a direct API primitive** (set `https://` FQDN → Traefik provisions LE); **no formal API deprecation policy** — pin version + regenerate from OpenAPI on upgrade; **no first-class rollback endpoint** and **public API returns only historical logs** (no realtime build-log stream).
- **Multi-server:** one Coolify drives many SSH-reachable Docker hosts; Swarm clustering is experimental; no k8s.

## Hetzner / IaC — key findings (no sidecar; captured here)
- **API:** REST `https://api.hetzner.cloud/v1`, `Authorization: Bearer` **token bound to one Project** → per-tenant isolation boundary. Async ops return **Action** objects to poll. **Rate limit 3,600 req/hr/token** (`RateLimit-*` headers, 429). Official **Go** SDK + `hcloud` CLI (no official Python SDK — community `hcloud-python`).
- **Compute/pricing (Apr + 15 Jun 2026 adjustments; re-verify live):** CX (x86 Intel) from ~€5.49, **CAX (ARM64) cheapest/core** ~€5.99, CPX (AMD), CCX (dedicated vCPU). **Hourly billing with monthly cap** — a server destroyed after hours costs only those hours (ideal for preview envs). **20 TB egress included**, €1/TB overage EU (vs ~$90/TB hyperscalers).
- **IaC:** **OpenTofu (MPL-2.0, LF-governed)** over **Terraform (BSL 1.1 — "no competing product" risk for a hosting product)**; both use official `hetznercloud/hcloud` provider. **Pulumi Automation API** = best structural fit for Python FastAPI (embeddable, no CLI subprocess, per-stack encrypted state).
- **Bootstrap:** cloud-init `user_data` (Hetzner passes it through) installs Docker + Coolify agent — **fire-and-forget; poll/agent-callback to confirm** (a failed `runcmd` doesn't fail the create call).
- **How reference platforms provision:** Fly = Firecracker microVMs; Railway = own bare-metal ("Metal"); Render = self-managed k8s on AWS; Vercel = Lambda + Fluid Compute. **None Terraform per request** — direct API / own fleet in the hot path.

## Notes
- Two streams (Coolify, Hetzner) returned inline and are summarized above rather than as separate files.
- Some magnitudes in the trend/AI report are vendor self-reported (flagged in-file). Re-verify the "re-verify before hard-coding" items in the plan (live Coolify OpenAPI, Hetzner port-25 policy + pricing, Gmail/MS PTR thresholds, Mailcow delegation limits) before building on them.
