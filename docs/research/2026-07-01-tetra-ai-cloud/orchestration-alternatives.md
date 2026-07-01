# Research: Container-deploy / orchestration backends for a multi-tenant hosting panel

> Note: This is a research deliverable, not a code-change plan. Facts verified against GitHub's
> API (stars/activity/license SPDX + raw LICENSE files) and official docs on 2026-07-01.
> Coolify baseline for comparison: `coollabsio/coolify`, Apache-2.0, ~57.7k stars, pushed 2026-07-01
> (source: GitHub API repos/coollabsio/coolify, 2026-07-01).

## 2. Alternatives / complements to Coolify

Two distinct classes appear below and they answer different questions for a hosting panel:

- **PaaS layers you'd sit *behind* (or replace Coolify with):** Dokploy, CapRover, Dokku. These
  already do app lifecycle + routing + TLS + databases, so a panel orchestrates *them* via API —
  the same integration shape Tetra Host already uses for Coolify.
- **Orchestration/deploy primitives you'd build *on top of*:** Kamal 2, Nomad, k3s/Kubernetes,
  Docker Swarm. These give scheduling/placement but little-to-no multi-tenant PaaS surface, so the
  panel would own more (tenant isolation, per-app routing, build pipeline).

### 2.1 Dokploy — the rising Coolify-like alternative — TRENDING UP

- **What it is:** Self-hostable open-source PaaS, explicitly positioned as an alternative to
  Vercel/Netlify/Heroku, and the most direct Coolify competitor (source: https://github.com/Dokploy/dokploy, 2026-07-01).
- **License:** Split license. Code outside a `/proprietary` directory is **Apache License 2.0**;
  content under `/proprietary` is under a separate proprietary license. GitHub reports the SPDX as
  `NOASSERTION` because of this split (source: raw `LICENSE.MD`, repos/Dokploy/dokploy, 2026-07-01).
  → Flag: the "open core" split means some functionality may be non-Apache; verify any feature you
  depend on isn't proprietary-licensed before building on it.
- **Architecture:** **Docker Swarm** for multi-node clustering; **Traefik** for routing/load
  balancing and automatic TLS. Native Docker Compose support; databases for MySQL, Postgres,
  MongoDB, MariaDB, libsql, Redis (source: https://github.com/Dokploy/dokploy, 2026-07-01).
- **API/automation:** Yes — **full REST API** with an `openapi.json` in the repo and Swagger docs,
  plus a CLI. This is the strongest signal for panel integration: you can drive it programmatically
  the same way Tetra Host drives Coolify (source: https://github.com/Dokploy/dokploy README, 2026-07-01).
- **Momentum:** **~35.3k stars**, latest release **v0.29.8 (2026-06-08)**, ~6,200 commits, **161
  releases**, repo pushed **2026-07-01** (sources: GitHub API repos/Dokploy/dokploy + README, 2026-07-01).
  Clearly the fastest-rising Coolify alternative.
- **Pros for a panel backend:** Same integration model as Coolify (REST + OpenAPI); Traefik/Swarm is
  a familiar, low-op stack; multi-node built in; active project.
- **Cons:** Open-core license split (proprietary directory) is a governance risk for a commercial
  multi-tenant product; younger and less battle-tested than Coolify; multi-tenancy is not a
  first-class isolation primitive (you'd still own tenant separation at the panel layer).

### 2.2 CapRover — mature, stable, slower-moving — STAGNANT / STEADY

- **What it is:** "Scalable PaaS (automated Docker+nginx) — aka Heroku on Steroids"
  (source: https://github.com/caprover/caprover, 2026-07-01).
- **License:** **Apache License 2.0** (source: raw `LICENSE`, repos/caprover/caprover — "Copyright
  2017-2024 BigZee Ventures LLC, Licensed under the Apache License, Version 2.0", 2026-07-01).
- **Architecture:** Docker Swarm + **nginx** reverse proxy (contrast with Dokploy/Traefik), with
  Let's Encrypt and one-click app templates (source: https://caprover.com/, 2026).
- **API/automation:** **No first-class public REST API.** Automation is via the CLI (`caprover api`
  is described as experimental) and a Bearer-token-secured API with permission levels
  (root/write/deploy/read); a typed TypeScript SDK exists but is experimental with **no guaranteed
  backward compatibility** (source: https://github.com/caprover/caprover-api + kloudshift/matthiasguentert
  comparison reviews, 2025-2026). → Flag: weaker automation story than Dokploy/Coolify; the panel
  would lean on an unstable API surface.
- **Momentum:** **~15.1k stars**, repo pushed **2026-05-18** (source: GitHub API repos/caprover/caprover,
  2026-07-01). Still maintained (commits reported into early 2026 in third-party reviews) but release
  cadence is slow and the project reads as feature-complete/mature rather than growing.
  → Flag: one search result reported "958 stars" for CapRover — that is **wrong/stale**; the GitHub
  API returns 15,074 stars as of 2026-07-01.
- **Pros for a panel backend:** Clean Apache-2.0; mature and stable; simple nginx+Swarm model;
  100M+ Docker Hub pulls indicate broad real-world use.
- **Cons:** No stable API contract to build a panel on (biggest issue for this use case); basic/buggy
  UI per reviews; slower development; no strong multi-tenancy story.

### 2.3 Dokku — Heroku-like, buildpack-native, plugin ecosystem — STEADY / MATURE

- **What it is:** "A docker-powered PaaS... the smallest PaaS implementation you've ever seen";
  Heroku-style git-push deploys (source: https://github.com/dokku/dokku, 2026-07-01).
- **License:** **MIT** © Jeff Lindsay (source: https://github.com/dokku/dokku, 2026-07-01). Most
  permissive of the group.
- **Architecture:** Docker under the hood; **Heroku/Cloud Native Buildpacks (herokuish)** for builds;
  git-push-to-deploy over SSH; nginx proxy by default. Built as a **collection of modular plugins**
  (Postgres, Let's Encrypt, backups, metrics, etc.) (source: https://dokku.com/docs/, 2025-2026).
- **API/automation:** Primarily **CLI + SSH + git**, not a REST API — automation is scripting the
  `dokku` command over SSH and writing plugins (any language, via triggers). An **HTTP REST API is
  planned but not yet the primary interface**; a paid **Dokku Pro** adds a web UI (recently migrated
  to React/Next.js) and is a **lifetime license** (source: https://dokku.com/docs/development/plugin-triggers/
  + https://dokku.com/blog/2025/pro-release-1.3.0/, 2025). → Flag: no mature REST API means a panel
  would shell out over SSH — workable but a different integration shape than Coolify/Dokploy.
- **Momentum:** **~32k stars**, latest release **v0.38.20 (2026-06-28)**, **340 releases**, repo
  pushed **2026-07-01** (source: GitHub API repos/dokku/dokku + README, 2026-07-01). Very steady,
  long-lived, actively maintained; growth is flat-but-healthy rather than surging.
- **Pros for a panel backend:** MIT (cleanest license); best buildpack story (no Dockerfile needed);
  huge, mature plugin ecosystem; extremely low resource footprint ($5 VPS).
- **Cons:** Single-host by design (no built-in multi-node clustering like Swarm/k8s); SSH/CLI-first
  automation instead of a REST API; multi-tenancy is DIY; richest UX is behind paid Dokku Pro.

### 2.4 Kamal 2 (basecamp/kamal) — a deploy tool, explicitly NOT a PaaS — TRENDING UP

- **What it is:** 37signals' container deploy tool — "Deploy web apps anywhere," from a $5 VPS to
  bare metal. Positioned as the anti-PaaS: DHH's launch post is literally titled *"Kamal 2: Thou need
  not PaaS"* (sources: https://github.com/basecamp/kamal + https://world.hey.com/dhh/kamal-2-thou-need-not-paas, 2024).
- **What it is NOT:** Not a PaaS. **No web dashboard, no server-side daemon/agent, no databases, no
  app catalog, no multi-tenant model.** It ships one containerized app (or a few) to servers you
  already own (source: https://dev.37signals.com/kamal-2/, 2024). → This is the key caveat for a
  hosting panel: Kamal gives you *deploy mechanics*, not a control-plane surface to integrate against.
- **Config/automation model:** Declarative **YAML** (`deploy.yml`) + a **CLI** that runs commands
  over **SSH** (via SSHKit) against target hosts; Docker does the running. Stateless — nothing
  persistent runs on the control side. A panel would generate/manage YAML and invoke the CLI rather
  than call an API (source: https://github.com/basecamp/kamal, 2026).
- **Proxy:** **kamal-proxy** (basecamp/kamal-proxy) — a purpose-built lightweight Go proxy replacing
  Traefik in v2; gives zero-downtime deploys, automatic Let's Encrypt TLS, and multiple apps on one
  host with a 1:1 mapping between kamal commands and proxy commands
  (sources: https://github.com/basecamp/kamal-proxy + https://kamal-deploy.org/docs/upgrading/proxy-changes/, 2024).
- **License:** **MIT** (source: https://github.com/basecamp/kamal, 2026).
- **Momentum:** **~14.4k stars**, latest release **v2.12.0 (2026-06-18)**, **72 releases**, used by
  ~20.7k projects, repo pushed **2026-07-01** (source: GitHub API repos/basecamp/kamal + README, 2026-07-01).
  Strong momentum, tied to Rails 8's "no PaaS required" default.
- **Pros for a panel backend:** MIT; dead-simple mental model; no daemon to babysit; kamal-proxy
  handles TLS + multi-app + zero-downtime; well-funded/maintained.
- **Cons:** **Not a control plane** — you'd build most of the panel (state, tenant isolation, DB
  provisioning, UI) yourself and drive Kamal as a shell-out deployer. No API; automating means
  wrapping the CLI and managing YAML per app. Wrong altitude if you want an off-the-shelf PaaS backend.

### 2.5 HashiCorp Nomad — general orchestrator, BUSL-licensed — MAINTAINED (license caveat)

- **What it is:** HashiCorp's general-purpose workload orchestrator/scheduler (containers + non-
  container workloads) — a lighter-weight alternative to Kubernetes (source: https://github.com/hashicorp/nomad, 2026).
- **License — read carefully:** In **August 2023 HashiCorp relicensed** from MPL-2.0 to the
  **Business Source License (BSL/BUSL) v1.1** across its products including Nomad; the repo SPDX is
  **BUSL-1.1** today (sources: https://www.hashicorp.com/en/license-faq +
  https://www.globenewswire.com/.../2723189/ (2023-08-10) + GitHub API repos/hashicorp/nomad, 2026-07-01).
  - Context: this is the same relicense that triggered the **OpenTofu** (Terraform) and **OpenBao**
    (Vault) community forks. **Nomad itself was NOT forked** — there is no widely-adopted Nomad fork
    equivalent to OpenTofu/OpenBao, so BUSL Nomad is effectively the only game in town.
  - What BUSL means practically: source-available, free to run in production **except** you may not
    offer Nomad as a competing commercial/hosted product; each release converts to MPL-2.0 after ~4
    years. HashiCorp now backports security/bugfixes to Community Edition for a 2-year window on 2.x
    (source: https://developer.hashicorp.com/nomad/docs/ce-license-support, 2025-2026).
  - → **Flag for Tetra Host:** a commercial multi-tenant hosting panel is exactly the kind of use the
    BUSL's "competing product" restriction is written to police. Using Nomad *internally* to run
    tenant workloads is likely fine; **legal review is warranted** before shipping it as the backing
    engine of a paid hosting product. Treat this as the single biggest adoption caveat here.
- **API:** Yes — a full **HTTP REST API** (repo has an `/api` dir; official API docs on
  developer.hashicorp.com), so a panel can drive it programmatically (source: GitHub API + docs, 2026).
- **Momentum:** **~16.7k stars**, latest release **v2.0.3 (2026-06-09)**, **255 releases**, repo
  pushed **2026-07-01**; Spring/Fall feature cadence with monthly patches (sources: GitHub API
  repos/hashicorp/nomad + https://developer.hashicorp.com/nomad, 2026). Actively maintained but a
  smaller ecosystem than Kubernetes.
- **Pros for a panel backend:** Solid HTTP API; multi-node scheduling without k8s complexity; runs
  mixed workloads; good bin-packing/placement.
- **Cons:** **BUSL licensing risk** for a commercial hosting product (biggest con); no built-in PaaS
  surface (build pipeline, TLS, per-tenant routing all DIY); smaller community/ecosystem than k8s;
  multi-tenancy via namespaces/ACLs is Enterprise-flavored and DIY at the panel layer.

### 2.6 k3s / Kubernetes — lightweight k8s as a backend — TRENDING UP (high op cost)

- **What it is:** **k3s** (k3s-io/k3s) is a CNCF-graduated, fully-conformant Kubernetes distribution
  in a single <100MB binary, runnable in ~512MB RAM; originally Rancher/SUSE
  (sources: https://www.cncf.io/projects/k3s/ + https://github.com/k3s-io/k3s, 2026).
- **License:** **Apache-2.0** (k3s), same as upstream Kubernetes (source: GitHub API
  repos/k3s-io/k3s, 2026-07-01). Cleanest license posture of the orchestrators here.
- **Architecture/API:** Full **Kubernetes API** — the most mature, best-documented, most extensible
  control-plane API in this list (CRDs, operators, RBAC). k3s swaps etcd for embedded SQLite/kine by
  default and bundles Traefik + a service load balancer (source: https://docs.k3s.io/, 2026).
- **Multi-tenancy story:** **Namespaces + RBAC + ResourceQuota/NetworkPolicy** give *soft* isolation;
  this is the natural per-tenant boundary for a panel. For *harder* isolation the 2025-2026 pattern is
  **vCluster** (virtual clusters, each with its own API server — often k3s/k0s inside) or **Capsule**
  (a CNCF `Tenant` CRD grouping namespaces with auto RBAC/quotas/policies)
  (sources: https://www.cncf.io/blog/2025/09/23/solving-kubernetes-multi-tenancy-challenges-with-vcluster/
  + https://srekubecraft.io/posts/k8s-multi-tenancy/, 2025-2026). → This is the **strongest native
  multi-tenancy story** of any option here.
- **Momentum:** k3s **~33.4k stars**, repo pushed **2026-06-30**; CNCF project with a large, growing
  ecosystem (source: GitHub API repos/k3s-io/k3s, 2026-07-01). Kubernetes overall remains the
  industry default and is trending up.
- **Pros for a panel backend:** Richest, most stable API to integrate against; genuine multi-tenancy
  primitives (namespaces + Capsule/vCluster) that map directly onto tenants; Apache-2.0; huge
  ecosystem (cert-manager, ingress, operators for DBs); horizontally scalable.
- **Cons:** **Highest operational cost** by far — you own a Kubernetes control plane, upgrades, CNI,
  storage, ingress, and a much larger security surface. Overkill unless you need real scale/multi-
  tenancy; steepest learning curve; no built-in build pipeline (need buildpacks/Kaniko/BuildKit).

### 2.7 Docker Swarm — is it dead? No, LTS-maintained but STAGNANT

- **Status in 2025-2026:** **Not dead, but not growing.** Docker Inc. handed Swarm to **Mirantis**,
  which has publicly **committed long-term support through at least 2030** (as part of Mirantis
  Kubernetes Engine 3) and continues security updates on a ~6-week cadence (3-week for CVEs)
  (sources: https://www.mirantis.com/blog/mirantis-guarantees-long-term-support-for-swarm/ +
  https://www.mirantis.com/blog/mirantis-will-continue-to-support-and-develop-swarm/, 2025-2026).
  Recent investment includes Seccomp API support and CSI (persistent storage) in MKE 3.
- **License:** Swarm mode is part of the Moby/Docker Engine, **Apache-2.0** (Moby project).
- **API:** Yes — the **Docker Engine API** (Swarm services/stacks/secrets/configs endpoints). Simple
  and stable; `docker stack deploy` from a Compose file is the ergonomic path.
- **Architecture:** Built into Docker Engine; managers + workers with Raft; overlay networking and
  routing mesh. Far simpler than k8s (source: Mirantis/Moby docs, 2026).
- **Momentum:** **Stagnant** — maintained and safe, but the mindshare, hiring pool, and new-feature
  velocity have moved to Kubernetes. It's a "safe legacy" choice, not a growth bet. Notably, the two
  rising PaaS layers above (**Dokploy** and **CapRover**) both build *on Swarm**, so Swarm remains
  relevant as an implementation detail even where its brand is fading.
- **Pros for a panel backend:** Simplest multi-node option; stable Engine API; low operational
  overhead; Compose-native; multiple PaaS layers already prove it works under a panel.
- **Cons:** Ecosystem/mindshare declining; thin multi-tenancy story (no namespaces — isolation is
  DIY via separate stacks/networks); future is a vendor (Mirantis) LTS commitment rather than
  community momentum; fewer new hires know it.

---

## Comparison table

| Tool | Class | License | API/automation | Architecture | Native multi-tenancy | Stars (2026-07-01) | Latest release | Trend |
|---|---|---|---|---|---|---|---|---|
| **Coolify** (baseline) | PaaS | Apache-2.0 | REST API | Docker + Traefik | Weak (panel-owned) | ~57.7k | active | UP |
| **Dokploy** | PaaS | Apache-2.0 + proprietary split | **Full REST API + OpenAPI + CLI** | Docker **Swarm** + **Traefik** | Weak (panel-owned) | ~35.3k | v0.29.8 (2026-06-08) | **UP** |
| **CapRover** | PaaS | Apache-2.0 | CLI + **experimental** API/SDK | Docker Swarm + **nginx** | Weak | ~15.1k | slow cadence | STAGNANT |
| **Dokku** | PaaS | **MIT** | CLI/SSH/git; REST **planned** | Docker + **buildpacks**, nginx | DIY (single-host) | ~32k | v0.38.20 (2026-06-28) | STEADY |
| **Kamal 2** | Deploy tool (NOT PaaS) | **MIT** | **CLI + YAML over SSH** (no API) | Docker + SSH + **kamal-proxy** | None | ~14.4k | v2.12.0 (2026-06-18) | **UP** |
| **Nomad** | Orchestrator | **BUSL-1.1** ⚠️ | HTTP REST API | Nomad scheduler, multi-node | Namespaces/ACL (Ent-leaning) | ~16.7k | v2.0.3 (2026-06-09) | MAINTAINED |
| **k3s / k8s** | Orchestrator | Apache-2.0 | **Kubernetes API** (richest) | Kubernetes (single binary) | **Strong** (ns + Capsule/vCluster) | ~33.4k (k3s) | active | **UP** |
| **Docker Swarm** | Orchestrator | Apache-2.0 (Moby) | Docker Engine API | Built into Docker Engine | Weak (no namespaces) | (part of Moby) | LTS→2030 (Mirantis) | STAGNANT |

---

## Bottom line for Tetra Host (a commercial multi-tenant panel)

- **Lowest-friction swap/complement to Coolify:** **Dokploy** — same integration model (REST +
  OpenAPI), Traefik/Swarm stack, trending up. Main caveat: the Apache/proprietary license split.
- **Cleanest license + most permissive:** **Dokku** (MIT) or **Kamal 2** (MIT), but both push more of
  the panel onto you (Dokku = SSH/CLI single-host; Kamal = deploy-only, no control plane).
- **Best long-term multi-tenancy / scale:** **k3s** (namespaces + Capsule/vCluster), at the price of
  the highest operational cost.
- **Watch the license:** **Nomad is BUSL-1.1** — get legal sign-off before backing a paid hosting
  product with it; unlike Terraform/Vault there is no community fork (no "OpenNomad").
- **Swarm** is safe-but-stagnant; you're already effectively using it transitively if you pick
  Dokploy or CapRover.

### Uncertainty flags
- Dokploy's exact split between Apache and proprietary features can change release-to-release — verify
  per feature before depending on it.
- CapRover star count in one search result ("958") was stale/incorrect; GitHub API says ~15.1k.
- Dokku's REST API is "planned"; confirm current state at implementation time.
- Nomad BUSL applicability to "a hosting panel" is a legal judgment, not settled fact — flagged for review.
