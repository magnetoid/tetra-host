## 4. Reverse proxy / edge routing

Scope: per-app subdomain routing plus automatic TLS at multi-tenant scale for a hosting control panel (Tetra Host orchestrates Coolify/Mailcow/Cloudflare), as of 2025–2026. This section compares **Traefik**, **Caddy** (incl. `caddy-docker-proxy`), and **nginx** (`nginx-proxy` / OpenResty). Every factual claim carries an inline citation. Uncertainty is flagged inline with **[UNCERTAIN]**.

The decisive question for a Vercel/Netlify-style product — where **customers point their own domains at us** — is *lazy / on-demand certificate issuance*. Everything else (labels, wildcards, HA) is secondary but material.

---

### 4.1 Traefik — label-based dynamic config, ACME/Let's Encrypt

**What it is / how it routes.** Traefik discovers Docker containers and configures routers from **labels** on the container. This is the model Coolify (default) and Dokploy use. Coolify: "By default, Coolify uses Traefik Proxy as its proxy, which comes with built-in container discovery… The Core team primarily uses Traefik" (source: https://coolify.io/docs/knowledge-base/server/proxies — accessed 2026-07-01). Dokploy: "a self-hosted PaaS that uses Docker Compose under the hood with Traefik as the reverse proxy" (source: https://docs.dokploy.com/docs/core/architecture — accessed 2026-07-01), and Dokploy is Traefik-only (source: https://x.com/ChristianLempa/status/2034230701311095048 — accessed 2026-07-01).

**Automatic TLS.** Traefik has a built-in ACME "certificate resolver" for Let's Encrypt supporting HTTP-01, TLS-ALPN-01, and DNS-01 challenges (source: https://doc.traefik.io/traefik/reference/install-configuration/tls/certificate-resolvers/acme/ — accessed 2026-07-01).

**Wildcards + Cloudflare DNS challenge.** Clean and well-trodden: "wildcard certificates can only be generated through a DNS-01 challenge" and "ACME V2 supports wildcard certificates" (source: https://doc.traefik.io/traefik/reference/install-configuration/tls/certificate-resolvers/acme/ — accessed 2026-07-01). With Cloudflare you set `CLOUDFLARE_DNS_API_TOKEN`, enable the DNS challenge, and Traefik writes/cleans the TXT record automatically (source: https://major.io/p/wildcard-letsencrypt-certificates-traefik-cloudflare/ — accessed 2026-07-01). This is a strong fit for `*.tenant.ourdomain.com` because one wildcard cert covers unlimited tenant subdomains, sidestepping per-subdomain issuance and Let's Encrypt rate limits entirely.

**License.** Traefik Proxy is open source (MIT). Advanced HA cert handling is pushed toward the paid **Traefik Enterprise** (source: https://doc.traefik.io/traefik/reference/install-configuration/tls/certificate-resolvers/acme/ — accessed 2026-07-01; corroborated https://ossalt.com/guides/traefik-vs-caddy-vs-nginx-reverse-proxy-self-hosting-2026 — accessed 2026-07-01). **[UNCERTAIN]** the exact SPDX license string wasn't confirmed from the repo in this pass; treat "MIT" as high-confidence-but-verify.

**Limitations at scale — the big one is HA cert storage.** Certificates are stored in a single `acme.json` file (source: https://doc.traefik.io/traefik/reference/install-configuration/tls/certificate-resolvers/acme/ — accessed 2026-07-01). The docs are explicit that this does **not** scale horizontally: "it is not possible to run multiple instances of Traefik 2.0 with Let's Encrypt enabled, because there is no way to ensure that the correct instance of Traefik receives the challenge request, and subsequent responses" (source: same URL — accessed 2026-07-01). The v1 KV-store option "was dropped in 2.0" for performance and has **not** been restored in v3 (source: same URL — accessed 2026-07-01). Their recommended HA path is **Traefik Enterprise** or an external controller like **cert-manager** (source: same URL — accessed 2026-07-01).

- Pros: default in Coolify/Dokploy (ecosystem familiarity, we already run Coolify); mature label model; clean DNS-01 wildcard story.
- Cons: **no built-in on-demand/lazy TLS for arbitrary customer domains** — you must know the domain to configure a router/cert; single-file `acme.json` blocks multi-instance HA on OSS; HA effectively requires paid tier or cert-manager.

---

### 4.2 Caddy — automatic HTTPS + On-Demand TLS (the multi-tenant answer)

**License.** Apache 2.0, fully open source (source: https://ossalt.com/guides/traefik-vs-caddy-vs-nginx-reverse-proxy-self-hosting-2026 — accessed 2026-07-01). **[UNCERTAIN]** confirm SPDX from github.com/caddyserver/caddy; Apache-2.0 is the widely-reported and expected value.

**On-Demand TLS — the killer feature for customer-supplied domains.** Caddy "dynamically obtain[s] a new certificate during the first TLS handshake that requires it, rather than at config load"; the handshake is held (a few seconds) while the cert is fetched, then cached (source: https://caddyserver.com/docs/automatic-https — accessed 2026-07-01). Crucially: "no config changes are required to serve more domains over HTTPS… perfect for servers hosting content or APIs for customer-owned domains because your HTTPS deployment scales as your business does" (source: https://caddyserver.com/on-demand-tls — accessed 2026-07-01). **This is the Vercel/Netlify pattern.** A customer CNAMEs their domain to us; on the first HTTPS hit Caddy issues the cert with no config edit and no restart.

**Abuse control — the `ask` endpoint (required).** "On-demand TLS must be both enabled and restricted to prevent abuse." The restriction is an **`ask` endpoint**: Caddy sends an HTTP GET `?domain=<name>`; a 2xx authorizes issuance (source: https://caddyserver.com/docs/automatic-https — accessed 2026-07-01). Practically: point `ask` at a small Tetra Host FastAPI endpoint that checks the tenant/custom-domains table and returns 200 only for domains a customer has actually registered. This is the mechanism that keeps on-demand issuance from being abused into Let's Encrypt rate-limit exhaustion.

**Built-in rate limiting (defense in depth).** "Caddy's internal rate limit is currently 10 attempts per ACME account per 10 seconds" (source: https://caddyserver.com/docs/automatic-https — accessed 2026-07-01), on top of whatever the CA enforces.

**HA / clustered cert storage — native, no paid tier.** "Any Caddy instances that are configured to use the same storage will automatically share those resources and coordinate certificate management as a cluster" (source: https://caddyserver.com/docs/automatic-https — accessed 2026-07-01). Point multiple Caddy nodes at shared storage (e.g. a storage plugin backed by Redis/Postgres/S3) and they coordinate issuance/renewal automatically — the exact thing Traefik OSS cannot do.

**Label-based config via `caddy-docker-proxy` (lucaslorentz).** MIT-licensed (source: https://github.com/lucaslorentz/caddy-docker-proxy — accessed 2026-07-01). It "scans Docker metadata for labels… generates an in-memory Caddyfile… [and on change] gracefully reload[s], with zero-downtime" (source: same URL — accessed 2026-07-01). Labels like `caddy: app.example.com` + `caddy.reverse_proxy: "{{upstreams 80}}"`. It supports a **controller/server split** via `CADDY_DOCKER_MODE` for clustered deployments (controller watches Docker and pushes config to server nodes) (source: same URL — accessed 2026-07-01). Warning from its docs: on swarms a persistent `/data` volume is "very important" to avoid re-issuing certs and hitting Let's Encrypt quotas on restart (source: same URL — accessed 2026-07-01).

**Wildcards + Cloudflare DNS challenge.** Supported, but the **default Caddy binary ships without DNS provider modules** — you must build with `xcaddy build --with github.com/caddy-dns/cloudflare` (source: https://dev.to/amanshaw4511/caddy-cloudflare-dns-wildcard-ssl-without-the-pain-4fn — accessed 2026-07-01; module: https://github.com/caddy-dns/cloudflare — accessed 2026-07-01). Then `*.foo.com { tls { dns cloudflare {env.CF_API_TOKEN} } }` gives automatic wildcard issuance + renewal (source: same DEV.to URL — accessed 2026-07-01). Token needs `Zone.Zone:Read` + `Zone.DNS:Edit` (source: same). Note `caddy-docker-proxy` also needs to be built with the DNS module for label-driven wildcards.

- Pros: **On-Demand TLS is the correct primitive for many custom customer domains**; native clustered cert storage (HA without a paid tier); Apache-2.0; zero-downtime label reloads via `caddy-docker-proxy`; Coolify already supports switching to Caddy.
- Cons: DNS-01/wildcard needs a **custom-built binary** (xcaddy); on-demand requires us to **build and operate the `ask` endpoint** (small, but it's ours to secure); Coolify labels Caddy support "experimental" and recommends Traefik for most setups (source: https://coolify.io/docs/knowledge-base/server/proxies — accessed 2026-07-01); on-demand handshake adds a few-second latency on first hit per new domain.

**[UNCERTAIN]** Whether On-Demand TLS can itself issue *wildcards* is not stated in the Caddy automatic-HTTPS docs (source: https://caddyserver.com/docs/automatic-https — accessed 2026-07-01). Assume: on-demand = per-hostname exact certs (via HTTP/TLS-ALPN challenge); wildcards are a separate DNS-01 configured path. Verify before relying on on-demand wildcards.

---

### 4.3 nginx — nginx-proxy / manual config / OpenResty

**What it is.** `jwilder/nginx-proxy` is "an auto-configurable reverse-proxy that routes traffic… to Docker containers," reacting to Docker events via the socket and rewriting nginx config + reloading; TLS is bolted on by a companion (`docker-letsencrypt-nginx-proxy-companion` / acme-companion) driven by `VIRTUAL_HOST` / `LETSENCRYPT_HOST` env vars (source: https://github.com/jwilder/docker-letsencrypt-nginx-proxy-companion — accessed 2026-07-01; corroborated https://techsch.com/tutorials/multiple-websites-jwilder-nginx-proxy-letsencrypt — accessed 2026-07-01).

**License.** nginx core is BSD-2-Clause; dynamic config / active health checks / JWT auth are gated behind paid **NGINX Plus** (source: https://ossalt.com/guides/traefik-vs-caddy-vs-nginx-reverse-proxy-self-hosting-2026 — accessed 2026-07-01). **[UNCERTAIN]** confirm BSD-2-Clause from nginx.org; it is the long-standing license.

**TLS + multi-tenant.** Works for multiple vhosts with automatic issuance/renewal (source: https://github.com/jwilder/docker-letsencrypt-nginx-proxy-companion — accessed 2026-07-01), but the model is **config-generation + full reload**: each new domain requires the domain to be known ahead of time (via env/label), a config regen, and an nginx reload. There is **no first-class on-demand/lazy issuance** equivalent to Caddy's; OpenResty (nginx + Lua) can script dynamic cert loading (`ssl_certificate_by_lua`) but that is a **build-it-yourself** system (e.g. lua-resty-auto-ssl), not an out-of-the-box product feature. **[UNCERTAIN]** exact reload behavior/limits at thousands of vhosts not quantified from primary sources in this pass.

- Pros: ubiquitous, battle-tested, highest raw performance ceiling; you can hand-tune anything.
- Cons: **no native on-demand TLS** (the core requirement); dynamic/multi-tenant behavior means config-regen + reload churn; the cleanest "many custom domains" path (OpenResty + Lua auto-ssl) is bespoke engineering; several dynamic features need paid NGINX Plus.

---

### 4.4 Let's Encrypt rate limits at scale (applies to all three)

These are the CA-level ceilings every proxy must respect (source: https://letsencrypt.org/docs/rate-limits/ — accessed 2026-07-01):

- **50 certificates per registered domain per 7 days** — this is the one that bites wildcard/subdomain strategies on a shared apex, and **overrides are available** for it (New Certificates per Registered Domain) via a request process.
- **300 new orders per account per 3 hours** (override available).
- **5 duplicate certificates (identical identifier set) per 7 days** (no override).
- **5 failed validations per identifier per hour** (no override).
- **ARI-coordinated renewals are exempt from all rate limits** (source: same URL).

Implications:
- **Wildcard strategy** (`*.tenant.ourdomain.com`): one cert covers all tenant subdomains → essentially immune to the per-domain issuance limit. Best for *our own* subdomains. Traefik and Caddy both do this via Cloudflare DNS-01.
- **Custom-domain strategy** (each customer's own apex/domain): each customer domain is its own registered domain, so the per-registered-domain limit rarely bites *us*, but the **300 orders / 3h account limit and the 5 failed-validations/hour** do — which is exactly why Caddy's `ask` endpoint (reject unknown domains before issuance) and internal 10/10s throttle matter. Request an account override if onboarding volume is high.

---

### 4.5 Recommendation

**Hybrid, Caddy-forward:**

1. **Tenant subdomains (`*.tenant.cloud-industry.com`)** → **wildcard cert via DNS-01 on Cloudflare** (we already integrate Cloudflare). One cert, no per-subdomain issuance, immune to rate limits. Works on either Traefik or Caddy.
2. **Customer-supplied custom domains (the Vercel/Netlify feature)** → **Caddy On-Demand TLS** behind an **`ask` endpoint served by Tetra Host** (query the tenant custom-domains table, return 200 only for verified domains). This is the only option here that issues certs lazily with zero config edits and scales as customers are added (source: https://caddyserver.com/on-demand-tls — accessed 2026-07-01). Neither Traefik OSS nor stock nginx-proxy offers this.
3. **HA**: run multiple Caddy nodes over **shared storage** so they coordinate as a cluster (source: https://caddyserver.com/docs/automatic-https — accessed 2026-07-01) — avoids Traefik OSS's single-`acme.json` ceiling and the Traefik Enterprise / cert-manager detour.

Pragmatic note: because our stack already runs **Coolify with Traefik as default**, the lowest-friction split is: keep Traefik for internal Coolify-managed app routing + wildcard tenant subdomains, and **add a Caddy edge tier dedicated to customer custom domains** (on-demand TLS + `ask`). Coolify explicitly supports switching to Caddy, but calls it experimental and recommends Traefik for general use (source: https://coolify.io/docs/knowledge-base/server/proxies — accessed 2026-07-01), so introducing Caddy as a *purpose-built custom-domain edge* rather than ripping out Traefik is the safer move. **nginx is not recommended** as the primary edge for this workload — no native on-demand TLS, and the dynamic custom-domain path is bespoke.

---

### 4.6 Comparison table

| Dimension | Traefik | Caddy (+ caddy-docker-proxy) | nginx (nginx-proxy / OpenResty) |
|---|---|---|---|
| License | MIT (OSS) **[verify SPDX]** | Apache-2.0 (OSS) **[verify SPDX]** | BSD-2-Clause core; NGINX Plus paid for dynamic features **[verify]** |
| Label-based Docker config | Yes (native; Coolify/Dokploy default) | Yes via `caddy-docker-proxy` (MIT, zero-downtime reload) | Yes via `nginx-proxy` (config-gen + reload) |
| Automatic TLS | ACME built-in (HTTP/TLS-ALPN/DNS) | Automatic HTTPS built-in | Companion container (acme-companion) |
| **On-demand / lazy TLS (custom customer domains)** | **No** | **Yes — On-Demand TLS + `ask` endpoint** | No native; OpenResty+Lua bespoke |
| Wildcard via Cloudflare DNS-01 | Yes, first-class | Yes, but needs custom build (xcaddy + caddy-dns/cloudflare) | Manual / companion |
| HA clustered cert storage | **No on OSS** (single acme.json); needs Enterprise or cert-manager | **Yes** (shared storage → auto cluster) | Manual (shared volume + external ACME) |
| Built-in issuance rate limiting | CA-level only | 10 attempts / ACME acct / 10s internal | CA-level only |
| Used by | Coolify (default), Dokploy | Coolify (experimental option) | Legacy / hand-rolled stacks |
| Best fit here | Internal app routing + wildcard tenant subdomains | **Customer custom-domain edge (Vercel-style)** | Not recommended as primary edge |

---

### Sources
- Caddy Automatic HTTPS (On-Demand, ask endpoint, internal rate limit, clustered storage): https://caddyserver.com/docs/automatic-https — accessed 2026-07-01
- Caddy On-Demand TLS marketing/overview (customer-owned domains scaling): https://caddyserver.com/on-demand-tls — accessed 2026-07-01
- lucaslorentz/caddy-docker-proxy (MIT, labels, CADDY_DOCKER_MODE, persistent /data): https://github.com/lucaslorentz/caddy-docker-proxy — accessed 2026-07-01
- caddy-dns/cloudflare module + xcaddy build for wildcard DNS-01: https://github.com/caddy-dns/cloudflare and https://dev.to/amanshaw4511/caddy-cloudflare-dns-wildcard-ssl-without-the-pain-4fn — accessed 2026-07-01
- Traefik ACME certificate resolver (acme.json, no multi-instance HA, KV dropped in 2.0, wildcard = DNS-01, Enterprise/cert-manager for HA): https://doc.traefik.io/traefik/reference/install-configuration/tls/certificate-resolvers/acme/ — accessed 2026-07-01
- Traefik + Cloudflare wildcard how-to: https://major.io/p/wildcard-letsencrypt-certificates-traefik-cloudflare/ — accessed 2026-07-01
- Coolify supported proxies (Traefik default, Caddy experimental): https://coolify.io/docs/knowledge-base/server/proxies — accessed 2026-07-01
- Dokploy architecture (Traefik): https://docs.dokploy.com/docs/core/architecture — accessed 2026-07-01
- Dokploy Traefik-only vs Coolify's switchable proxy: https://x.com/ChristianLempa/status/2034230701311095048 — accessed 2026-07-01
- jwilder nginx-proxy + letsencrypt companion: https://github.com/jwilder/docker-letsencrypt-nginx-proxy-companion — accessed 2026-07-01
- Let's Encrypt rate limits (50/registered domain/wk, 300 orders/3h, 5 dup/wk, 5 failed/hr, ARI exempt, overrides): https://letsencrypt.org/docs/rate-limits/ — accessed 2026-07-01
- License comparison corroboration: https://ossalt.com/guides/traefik-vs-caddy-vs-nginx-reverse-proxy-self-hosting-2026 — accessed 2026-07-01
