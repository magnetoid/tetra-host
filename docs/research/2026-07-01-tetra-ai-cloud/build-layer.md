# Research deliverable: Build layer (source-to-container)

This file holds the research output requested. See the section below.

## 3. Build layer (source-to-container)

The build layer is the part of a PaaS/hosting panel that turns a Git repo (or uploaded
source) into a runnable OCI container image, ideally with **zero developer config**. In
2025-2026 there are four practical strategies a Vercel-like panel can offer: **Nixpacks**,
**Railpack**, **Cloud Native Buildpacks (CNB)**, and **explicit Dockerfile / static
builds**. Below is how each works, its maturity, and the tradeoffs.

---

### 3.1 Nixpacks (`railwayapp/nixpacks`) — the incumbent, now in maintenance mode

**What it is.** An open-source, zero-config source-to-image builder created by Railway:
"App source + Nix packages + Docker = Image." It produces OCI-compliant images without a
Dockerfile, using the **Nix** package manager for OS/language-level dependencies (e.g.
`nodejs`, `ffmpeg`) (source: https://github.com/railwayapp/nixpacks, fetched 2026-07-01;
https://nixpacks.com/docs, 2026-07-01).

**How source-to-container works.** Two phases (source: https://nixpacks.com/docs/how-it-works, 2026-07-01):
1. **Plan** — analyze the source dir, detect language/framework by matching against
   *providers*. Each provider proposes Nix packages plus **install**, **build**, and
   **start** commands (all user-overridable). Providers define three standard phases:
   *setup* (install Nix packages), *install* (fetch build deps), *build* (compile/prepare).
2. **Build** — Nixpacks generates a Dockerfile from the plan and builds it with **Docker
   BuildKit**, emitting an OCI image runnable anywhere.

**Who uses it.** Railway (its origin) and **Coolify**, where Nixpacks is still the default
build pack (source: https://coolify.io/docs/applications/build-packs/overview, 2026-07-01).
Many self-hosted panels standardized on it because it needs no per-repo config.

**License / language / maturity.** MIT; written in Rust (~86%); 3.5k GitHub stars, latest
release v1.41.0 (Oct 2025). **The README now states it is in maintenance mode and not under
active development, and directs users to Railpack as the replacement** (source:
https://github.com/railwayapp/nixpacks, 2026-07-01).

**Limitations.**
- **Huge images.** Nix produces a single monolithic `/nix/store` layer, yielding large
  images and poor cache reuse (source: https://blog.railway.com/p/introducing-railpack, 2026-07-01).
- **Coarse versioning.** Nix's package set only reliably exposes the *latest major* of each
  package; pinning `major.minor.patch` is awkward (source: same blog).
- **Nix learning curve** for anything beyond the happy path.
- **Frozen feature set** — critical bug fixes only, no new language providers (source:
  Coolify issue #7983, https://github.com/coollabsio/coolify/issues/7983, 2026-07-01).

---

### 3.2 Railpack (`railwayapp/railpack`) — Nixpacks' successor  ⚠️ still maturing

**What it is.** Railway's ground-up replacement for Nixpacks: a zero-config builder that
"automatically analyzes and turns your code into an image," built on lessons from running
Nixpacks across millions of builds in production (source:
https://github.com/railwayapp/railpack, 2026-07-01;
https://blog.railway.com/p/introducing-railpack, 2026-07-01).

**Why Railway built it.** The blog frames Nixpacks as working for only ~80% of users and
being a scaling bottleneck. The three headline wins (source: blog, 2026-07-01):
- **Smaller images** — reductions of **~38% (Node) to ~77% (Python)** vs Nixpacks, by
  dropping the monolithic `/nix/store` layer.
- **Better caching** — Railpack interfaces **directly with BuildKit** (custom **LLB** +
  a custom **BuildKit frontend**), giving fine-grained, layer-level, **shareable caches
  across environments** rather than one opaque Nix layer.
- **Granular versioning** — real `major.minor.patch` runtime version selection.

**How it differs from Nixpacks technically.**
- Codebase rewritten **Rust → Go**, specifically to use the BuildKit Go libraries
  (source: blog, 2026-07-01).
- **No Nix.** Railpack builds its own BuildKit LLB graph instead of generating a Dockerfile
  and shelling out to Nix. Running it standalone requires a BuildKit daemon
  (`BUILDKIT_HOST=docker-container://buildkit`) (source:
  https://github.com/railwayapp/railpack, README, 2026-07-01).
- License **MIT** (same as Nixpacks).

**Status — flag uncertainty here.**
- Railpack is **beta**. Railway's own docs/UI and the launch blog label it beta; it "powers
  builds for railway.com and central station" and is opt-in on Railway (source: blog,
  2026-07-01).
- **Launch date: I assess March 2025, not 2026, despite conflicting search summaries.** The
  blog post header renders "March 4" and some search snippets said "March 4, 2026," but
  Railway's own changelog URLs are dated `2025-03-14-ssh-railpack-improvements` and
  `2025-03-21` (source: https://railway.com/changelog/2025-03-14-ssh-railpack-improvements),
  and the repo already has 123+ releases up to ~v0.30.0 by mid-2026 — a release cadence only
  consistent with a **March 2025** launch. Treat "2026" launch claims in secondary blogs as
  errors. (Confidence: high that it is early/March 2025; the exact day is secondary.)
- **Narrower language coverage than Nixpacks.** As of the launch it deliberately prioritized
  *depth over breadth*: **Node, Python, Go, PHP, and static HTML** (plus JS frameworks like
  Vite, Astro, CRA, Angular). Languages Nixpacks handled — **Rust, Ruby, Java, and others —
  were not yet in Railpack** at launch (source: blog, 2026-07-01; Coolify discussion #5282 /
  issue #7983, 2026-07-01). This gap narrows over time, so verify current provider coverage
  before committing.

**Is anyone besides Railway adopting it?** Yes — **Coolify merged first-class Railpack
support (PR #9117) on ~2026-05-11**, exposing it across app creation, settings, the API, and
for regular/preview/static apps, with a **beta** label in the UI. Notably, **Coolify kept
Nixpacks as the default and reverted Railpack from being the default** in new-app flows —
i.e. Railpack is offered but not yet trusted as the default (source:
https://github.com/coollabsio/coolify/pull/9117, 2026-07-01). This is the single most
important real-world signal on Railpack maturity: adopted, not yet defaulted.

---

### 3.3 Cloud Native Buildpacks (CNB, `buildpacks.io`) — the CNCF standard

**What it is.** A **CNCF incubating** project (started by Pivotal + Heroku Jan 2018, joined
CNCF Oct 2018) that standardizes source-to-image via a spec-defined **platform ↔ buildpack**
contract. It transforms app source "into images that can run on any cloud" and centralizes
container-build expertise so app teams don't each maintain Dockerfiles (source:
https://buildpacks.io/, 2026-07-01).

**How source-to-container works.**
- **`pack` CLI** is the entry point. You run `pack build <image> --builder <builder>`.
- A **builder** = a base build image + a set of **buildpacks** + a lifecycle. Each buildpack
  runs a **detect** step (does this app match?) then a **build** step (contribute layers).
- The **lifecycle** orchestrates detect → build → export into an OCI image, producing
  **discrete, well-labeled layers** (source: https://buildpacks.io/docs/, 2026-07-01).

**Distinguishing features vs Nixpacks/Railpack.**
- **Rebase** — swap the OS base image of an *already-built* image **without rebuilding the
  app**, using OCI cross-repo blob mounting / layer rebasing on Docker registry v2. This
  makes OS-CVE patching near-instant across a fleet — something Nixpacks/Railpack don't offer
  (source: https://buildpacks.io/, 2026-07-01).
- **Reproducibility** — bit-for-bit reproducible builds where supported (source:
  https://pradeepl.com/blog/kubernetes/cloudnativebuildpacks/, 2026-07-01).
- **SBOM / provenance** maturity from being a security-reviewed CNCF project (source:
  https://tag-security.cncf.io/community/assessments/projects/buildpacks/, 2026-07-01).

**Buildpack suites / who uses it.** Buildpack collections are maintained by **Paketo**
(open-source, broad language coverage), **Heroku** (its CNB buildpacks power the Heroku
platform), and **Google Cloud** (source: https://buildpacks.io/, 2026-07-01;
https://github.com/heroku/buildpacks, 2026-07-01). Platforms using CNB include Heroku, and
historically Tanzu/Pivotal, plus anything driving `pack`/`kpack` in CI.

**License.** Apache-2.0 (CNB spec, lifecycle, and pack are Apache-2.0; Paketo/Heroku
buildpacks likewise Apache-2.0). (Confidence: high for the umbrella; verify per-buildpack.)

**Pros vs Nixpacks.** Vendor-neutral standard, rebase, reproducibility, SBOMs, mature
enterprise pedigree, huge language coverage via Paketo.

**Cons vs Nixpacks/Railpack.** Heavier and slower to first build; more moving parts
(builders, stacks, lifecycle); more configuration surface; base images can be large; the DX
is more "platform engineering" than "push and go." For a lean self-hosted panel it's more
infra to operate.

---

### 3.4 Static sites and Dockerfile-based builds — the escape hatches

Every serious panel offers, alongside auto-detection, two explicit modes:

**Static build.** For pure static output (Astro, Jekyll, Vite/React build, plain HTML). In
Coolify the flow is: build the site from the repo, then produce a Docker image running a web
server (**Nginx**, the only server as of v4.0.0-beta.404) that serves a configured **publish
directory** (e.g. `/dist`) on **port 80** (source:
https://coolify.io/docs/applications/build-packs/nixpacks, 2026-07-01). Railpack also has a
native **static HTML** path (source: blog, 2026-07-01). This is the closest analog to
Vercel's static hosting, though a true Vercel-like DX usually wants a CDN/edge in front of
the container rather than shipping Nginx-in-a-container per site.

**Dockerfile build.** For full control / unsupported stacks, the panel builds the repo's
own `Dockerfile` (and Coolify additionally supports **Docker Compose** for multi-service
apps) (source: https://coolify.io/docs/applications/build-packs/overview, 2026-07-01). This
is the universal escape hatch: auto-detect covers the 80% path; a committed Dockerfile
covers everything else. A good panel auto-selects the build pack (detect Dockerfile → use it;
else run the auto-builder) while letting the user override.

---

### 3.5 Recommendation for a Vercel-like DX panel in 2026

**Tiered strategy, not a single builder:**

1. **Default auto-builder → Railpack, with Nixpacks as fallback.** Railpack is the strategic
   direction (Nixpacks is EOL/maintenance-only), gives the smaller images and better BuildKit
   caching a fast-deploy DX needs, and is MIT + BuildKit-native. **But** because it is still
   **beta** with **narrower language coverage**, mirror Coolify's real-world posture:
   **offer Railpack, keep Nixpacks available**, and pick per-repo based on detected language.
   (source for both statuses: railpack blog + Coolify PR #9117, 2026-07-01.)
2. **Dockerfile / Compose escape hatch** — always honor a committed `Dockerfile`; it's the
   only way to cover the long tail without shipping new providers.
3. **First-class static path** — detect static frameworks and serve them cheaply; ideally
   front them with a CDN/edge rather than per-site Nginx containers if you want true Vercel-grade DX.
4. **Consider CNB only if** you need enterprise-grade **rebase** (instant fleet-wide base-image
   CVE patching), reproducibility, and SBOM/provenance — at the cost of heavier build infra
   and worse cold-build latency. It's the "compliance/scale" option, not the "fast DX" option.

**Net:** for a Vercel-like DX in 2026, the winning combination is **Railpack (primary,
watching its beta status) + Nixpacks (fallback) + Dockerfile/Compose + a static path**, with
**CNB held in reserve** for teams that specifically need rebase/reproducibility/SBOM.

---

### Uncertainty log (explicit)
- **Railpack launch date:** high confidence it is **early/March 2025** (Railway changelog
  URLs + 123-release history), *not* the "March 2026" some secondary blogs and search
  summaries stated. Exact day less certain.
- **Railpack current language coverage:** it was Node/Python/Go/PHP/static at launch and has
  been expanding; **re-check the provider list before relying on Rust/Ruby/Java/etc.**
- **Railpack "GA vs beta":** still labeled beta by Railway and by Coolify's UI as of the
  data gathered (2026-07-01); no confirmed GA declaration found.
- **CNB / Paketo license:** stated Apache-2.0 for the umbrella from general knowledge +
  CNCF status; buildpacks.io page itself showed only a copyright line — verify per component.
