# Vercel-like DX on an Open-Source Coolify Orchestrator

*Research section. All access dates: 2026-07-01 (today). Coolify facts current as of the v4.1.2 (2026-06-04) release line. Flags mark anything unverified.*

---

## 1. Git push-to-deploy

**How Coolify handles git sources today (verified):** Coolify supports four+ ingestion paths, in descending order of capability:

- **GitHub App (recommended, full-featured).** Coolify installs a GitHub App with per-repo granular permissions. It **auto-configures the webhook**, enables Auto Deploy by default, posts **commit check statuses** (pending → success/failure), and is the *only* path that unlocks **PR preview deployments** and **automated PR comments**. Every push to the configured deploy branch triggers a rebuild with no extra config. (coolify.io/docs/applications/ci-cd/github/auto-deploy; coolify.io/docs/applications/ci-cd/github/preview-deploy — accessed 2026-07-01)
- **GitHub OAuth (Git Source).** Lighter integration; does **not** support previews. (Same docs.)
- **Manual webhooks + deploy keys.** For GitLab/Bitbucket/Forgejo/Gitea/self-hosted: add a Coolify-generated webhook URL to the repo, set a shared **webhook secret**, and add a **deploy key (private SSH key)** for private repo clone. Push events trigger deploys. (coolify.io/docs/applications/ci-cd/gitlab/integration; coolify.io/docs/applications/ci-cd/bitbucket/integration — accessed 2026-07-01)
- **GitLab OAuth Git Source** with callback `…/webhooks/gitlab` and scopes `api, read_repository, email`. (Same GitLab docs.)

**Webhook signature verification pattern (verified + general):** Coolify's model is a shared secret configured on both sides; GitHub HMAC-signs the payload (`X-Hub-Signature-256`) and Coolify rejects any request whose signature doesn't match. SSL verification must be on. Only `push` events deploy (PR events flow through the App path). The canonical pattern to replicate in Tetra: `hmac.new(secret, raw_body, sha256)` compared in **constant time** against the provider header, per-project distinct secrets. (coolify.io/docs/applications/ci-cd/github/auto-deploy — accessed 2026-07-01)

**`[skip ci]`/`[skip cd]` support** landed in **v4.1.0 (2026-05-18)** for webhook commits and PR/MR titles. (coolify.io/changelog — accessed 2026-07-01)

- (a) **OSS building blocks:** GitHub's official `githubapp`/`octokit` libraries, `python-gitlab`, HMAC verification (stdlib), `smee.io` for local webhook relay. Provider-agnostic: [webhooks are just signed HTTP POSTs].
- (b) **Coolify provides** the whole push→deploy loop already. **Build on top:** a *unified* multi-tenant App registration surface (Coolify's GitHub App is one App per Coolify instance; a SaaS panel wants one App per tenant org or a shared App with per-install routing — [verify Coolify's single-App-per-instance assumption holds for multi-tenant]).

---

## 2. Preview / ephemeral environments per branch/PR

**Vercel/Netlify baseline:** every push/PR gets an immutable, uniquely-URL'd deployment; serverless scale-to-zero makes keeping every historical build cheap. (vercel.com/docs/deployments — accessed 2026-07-01)

**Coolify preview deployments — CURRENT STATE (verified, feature is mature):**
- Per-PR isolated environment with a **configurable subdomain template**: `{{pr_id}}` or `{{random}}`, requiring a **wildcard DNS A record** at the server. (coolify.io/docs/applications/ci-cd/github/preview-deploy — accessed 2026-07-01)
- **Automatic teardown** when the PR is merged/closed.
- **Automated PR status comments** (GitHub App only; needs PR read/write perms + PR event subscription).
- **Env var scoping:** production vars are isolated and never exposed to previews; previews get their own set.
- **Security gating:** default only members/collaborators/contributors can trigger previews; fork-PR safety hardened. There was a documented **fork-PR security risk** historically (discussion #3046) — recent releases added "improved fork pull request safety."
- **API:** `DELETE` endpoint to remove a preview deployment **by PR id** shipped in **v4.1.2 (2026-06-04)**.
- Recent fixes: per-volume PR-suffix control (beta.469, 2026-03-20); preview image tag isolation per commit (v4.1.0/v4.1.2); Compose-generated env vars no longer break previews (v4.1.2). (coolify.io/changelog — accessed 2026-07-01)

- (a) **OSS building blocks:** wildcard DNS + wildcard/on-demand TLS (see §6), Traefik dynamic routing, GitHub App PR-comment API.
- (b) **Coolify provides** per-PR spin-up, subdomain routing, teardown, PR comments, and env scoping. **Build on top:** cross-provider PR comment bot if you want it branded/aggregated; DB branching for previews (Coolify doesn't branch databases — the PostgresAI/DBLab pattern bolts that on externally; [verify no native DB-branching in Coolify]); tenant-level quotas on concurrent previews.

---

## 3. Instant rollback

**How it works generally:** Vercel's "Instant Rollback" **reassigns the domain/alias to an already-built immutable deployment** — no rebuild, traffic reroutes in ~1s. The enabling property is immutable, retained build artifacts. (vercel.com/docs/instant-rollback — accessed 2026-07-01)

**Coolify — CURRENT STATE (verified):** Coolify supports **one-click rollback** from the app's Deployments tab. Every deployment is listed with commit hash/timestamp/status; selecting a prior successful deployment + Rollback **redeploys the exact local Docker image without rebuilding**. **Constraint: only locally-available images** — rollback targets a locally cached image, governed by a **"keep for rollback"** retention setting (respected for Nixpacks build images as of beta.466, 2026-03-11). (coolify.io/docs/applications; coolify.io/changelog — accessed 2026-07-01)

- (a) **OSS building blocks:** immutable image tags per deploy (registry-pushed), atomic Traefik router swap, retention policy.
- (b) **Coolify provides** UI rollback via cached images. **Build on top / GAPS:** (i) rollback is **not clearly exposed as a REST endpoint** — the Application API docs list start/restart/stop but **no documented rollback endpoint** ([verify against live OpenAPI 3.1 spec at coolify.io/docs/api-reference]); a panel likely needs to trigger a `start`/deploy pinned to a prior image tag/commit, or drive it out-of-band. (ii) Local-image-only means rollback breaks if the image was evicted — a robust panel should **push every build to a registry** and manage retention itself. (deepwiki.com/coollabsio/coolify/8.2-application-api-endpoints — accessed 2026-07-01)

---

## 4. Build-log streaming

**Real-time patterns (general):** **SSE** (one-way server→client, auto-reconnect, trivial over HTTP/proxies) is the usual fit for append-only build logs; **WebSocket** when you need bidirectional/interactive. Docker/BuildKit/Nixpacks/Railpack all emit line-oriented stdout you can tail and forward.

**Coolify — CURRENT STATE (verified, with a gap):**
- The **UI** shows real-time build+deploy logs (Coolify uses Laravel Livewire/websockets internally).
- The **CLI** (`coolify app deployments logs <app-uuid> [deployment-uuid]`) supports **`--follow` (tail -f style)** and debug logs.
- The **public REST API** exposes an endpoint to fetch **container logs** for running apps, but this returns **historical logs, not a real-time stream**, and the Application API docs **do not expose a build/deployment-log endpoint**. So programmatic *build-log streaming* over the documented API is a **gap**. (coolify.io/docs/knowledge-base/drain-logs; github.com/coollabsio/coolify-cli; deepwiki.com/coollabsio/coolify/8.2-application-api-endpoints — accessed 2026-07-01)
- Log **drains** (ship logs to external sinks) are documented. (coolify.io/docs/knowledge-base/drain-logs — accessed 2026-07-01)

- (a) **OSS building blocks:** SSE via `sse-starlette`/FastAPI `StreamingResponse`; poll-and-diff the Coolify container-log endpoint; or subscribe to Coolify's internal websocket/Laravel Echo channel ([undocumented/unstable — verify]); log drain → your own store → re-stream.
- (b) **Coolify provides** UI + CLI live logs. **Build on top:** a Tetra `/deployments/{id}/logs` SSE endpoint that either proxies the CLI/websocket or polls the container-log API and re-emits as SSE (matches Tetra's existing `tetra deploy --follow`).

---

## 5. Environment variables / secrets management

**Coolify — CURRENT STATE (verified, quite capable):**
- **Two independent flags per var: Build Variable / Runtime Variable** (both on by default). Disable Build to keep a secret out of the image build entirely. (coolify.io/docs/knowledge-base/environment-variables — accessed 2026-07-01)
- **Runtime injection:** after build, Coolify writes a `.env` on the target server, loaded via Compose `env_file` at container start. **Build-time secrets are overwritten before the container starts** (two-phase strategy → build secrets don't leak into runtime).
- **Docker BuildKit build secrets:** enabling "Use Docker Build Secrets" makes Coolify auto-rewrite `RUN` into `--mount=type=secret` so secrets never land in image layers.
- **`Is Secret?`** → write-only masking; value hidden in UI/logs after save.
- **Prod vs preview scoping** is first-class (see §2).
- **API:** `GET/POST /applications/{uuid}/envs`, `PATCH …/envs/bulk`, `DELETE …/envs/{env_uuid}` — individual + bulk. (deepwiki.com/coollabsio/coolify/8.2-application-api-endpoints — accessed 2026-07-01)

- (a) **OSS building blocks:** SOPS/age or Vault/Infisical/OpenBao for encryption-at-rest in *your* control plane; sealed secrets patterns.
- (b) **Coolify provides** per-env scoping, build-vs-runtime split, BuildKit secret mounts, masking, and a full env CRUD API. **Build on top:** encryption-at-rest of secrets in **Tetra's own DB** before they reach Coolify ([verify how Coolify stores env values at rest — masking ≠ encryption-at-rest guarantee]); audit trail of secret changes (Coolify added structured audit logging for API mutations in v4.1.0, 2026-05-18 — leverage it).

---

## 6. Custom domains + automatic TLS at scale

**Coolify proxy/TLS — CURRENT STATE (verified):**
- Default proxy is **Traefik**. Adding a custom domain triggers an automatic **ACME HTTP-01** challenge with Let's Encrypt (temp file served on :80). (coolify.io/docs/knowledge-base/proxy/traefik/wildcard-certs; eventuallymaking.io — accessed 2026-07-01)
- **Wildcard certs** (needed for `*.preview.example.com`) require **DNS-01**, which needs Traefik to have **DNS-provider API access** (Cloudflare, Route53, Hetzner, etc. via Lego). HTTP-01 can't issue wildcards.
- **Caddy** is available but secondary; Caddy's `tls internal` gives per-service self-signed.
- **v4.0.0-beta.467 (2026-03-11):** database-backed proxy config with versioned backups + auto-recovery — relevant for reliability at scale. (coolify.io/changelog — accessed 2026-07-01)

**TLS for thousands of *customer* custom domains (the hard problem):**
- **Caddy On-Demand TLS** is the canonical OSS pattern: cert is obtained **during the first TLS handshake** for an unseen SNI, gated by an **"ask" endpoint** — Caddy HTTP-GETs your API with the hostname; you return 200 only for domains in your tenant DB. Subsequent handshakes are cached/fast; renewals are background. This scales custom domains without pre-provisioning certs. (caddyserver.com/on-demand-tls; caddyserver.com/docs/automatic-https; fivenines.io 2026 guide — accessed 2026-07-01)
- **Cloudflare for SaaS (SSL for SaaS) / Custom Hostnames** is the managed alternative: **thousands of custom hostnames per zone** with no per-hostname infra, automatic **DCV** (Cloudflare answers the validation token on the customer's behalf when they CNAME to you), dual cert chains (ECDSA P-256 + RSA-2048) for compatibility. Good when you don't want to run cert issuance yourself. (developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/ — accessed 2026-07-01)

- (a) **OSS building blocks:** Traefik + DNS-01 (wildcard, for *your* preview subdomains); **Caddy On-Demand TLS + ask endpoint** (for *customer* apex/vanity domains); step-ca for private CA.
- (b) **Coolify/Traefik provides** per-app HTTP-01 and wildcard-via-DNS-01. **Build on top:** on-demand TLS for arbitrary customer domains is **not** Coolify's model out of the box — either front Coolify with a Caddy layer running the ask-endpoint against Tetra's tenant/domain table, **or** use Cloudflare for SaaS custom hostnames (Tetra already integrates Cloudflare DNS, so the API surface is familiar). [Verify whether to terminate customer TLS at a Tetra edge vs. inside Coolify's Traefik.]

---

## Cross-cutting: Coolify API maturity (2025-2026)

- **REST, `/api/v1`, Laravel-backed, OpenAPI 3.1**, **Sanctum bearer tokens** with **scoped permissions** (`read`/`write`/`deploy`). Five distinct app-creation endpoints keyed by git-auth method × build strategy. (deepwiki.com/coollabsio/coolify/8-api-reference; deepwiki.com/coollabsio/coolify/8.2-application-api-endpoints — accessed 2026-07-01)
- **v4.1.x maturation (2026):** deployment config **diff tracking** (pending/build-impacting changes surfaced pre-redeploy, v4.1.0/v4.1.2); **structured audit logging** for API mutations/webhooks/auth (v4.1.0); API-token expiration warnings (beta.471); preview-deployment DELETE-by-PR endpoint (v4.1.2). (coolify.io/changelog — accessed 2026-07-01)
- **Documented gaps for a higher-level panel:** no first-class **rollback** REST endpoint; no real-time **build-log stream** over the public API (historical container logs only); build-log/deploy-log retrieval not in the Application API docs. These are the main "must build a shim" areas. [Verify against the live OpenAPI spec, which may be ahead of DeepWiki's mirror.]

## Cross-cutting: Buildpacks options (2025-2026)

- **Nixpacks** — Coolify's long-standing default; **maintenance mode since 2025** (critical fixes only, no new providers). Known issues: huge single `/nix/store` layer, non-semver Nix pinning. (github.com/railwayapp/nixpacks; blog.railway.com/p/introducing-railpack — accessed 2026-07-01)
- **Railpack** — Railway's Nixpacks successor: **Go + BuildKit**, Ubuntu base + standard package managers, true multi-phase layered builds, **semver package pinning**, image-size cuts ~38% (Node)–77% (Python). GA'd beta 2026-03-04. **Now a beta build-pack option inside Coolify as of v4.1.0 (2026-05-18)** with build-time env support. (blog.railway.com/p/introducing-railpack; coolify.io/changelog — accessed 2026-07-01)
- **Dockerfile** and **Docker Compose** — first-class in Coolify; most control.
- **Cloud Native Buildpacks (Paketo/Heroku)** — mature OSS standard, but **not a native Coolify build strategy** per current docs ([verify]); would require Dockerfile-wrapping or external build.
- **Static** sites — native Coolify strategy.

---

## Implication for Tetra

Coolify already delivers most of the Vercel signature loop natively — GitHub-App push-to-deploy, mature per-PR **preview deployments** with wildcard subdomains + auto-teardown + PR comments, **one-click rollback**, prod/preview **env scoping** with BuildKit build-secret support, and automatic **Traefik + Let's Encrypt** TLS — all behind a scoped `/api/v1` (OpenAPI 3.1, Sanctum). So Tetra's job is **orchestration and DX polish, not reimplementation**: expose these through Tetra's tenant-aware panel and keep dashboard↔CLI parity (`tetra deploy --follow`, a new `tetra preview`/`tetra rollback`). The concrete build-on-top work concentrates in four gaps: (1) a **build-log SSE shim** because the public API only returns historical container logs (poll/proxy → re-stream); (2) a **rollback path** since there's no documented rollback REST endpoint (pin-and-deploy a prior image, and push every build to a registry so rollback doesn't depend on local image eviction); (3) **customer custom-domain TLS at scale**, which Coolify's per-app ACME model doesn't cover — front it with **Caddy On-Demand TLS + an ask-endpoint** hitting Tetra's domain table, or lean on **Cloudflare for SaaS custom hostnames** (Tetra already speaks Cloudflare); and (4) **multi-tenant secret custody** — encrypt secrets at rest in Tetra's own store before handing them to Coolify, and consume Coolify's new structured audit log. Adopt **Railpack** (now beta in Coolify v4.1.0) as the forward default over maintenance-mode Nixpacks. Flag for verification before committing designs: exact live OpenAPI surface (rollback/logs), Coolify's env-value at-rest storage, native DB-branching for previews, and whether one GitHub App per Coolify instance is workable for many tenant orgs.
