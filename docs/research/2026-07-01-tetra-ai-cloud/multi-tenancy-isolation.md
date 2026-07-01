# Multi-Tenancy & Isolation for an Untrusted-Multi-Tenant PaaS/Hosting Platform

*Research section — current as of July 2026. Every claim carries a source URL + access date (all accessed 2026-07-01). Primary/official sources prioritized. Uncertainty is flagged inline with **[UNVERIFIED]** or **[APPROX]**.*

---

## 1. Patterns for hard tenant isolation in a hosting platform

### Resource limits via cgroups v2 (and how Docker/Podman map to them)

Modern Linux hosts default to the **unified cgroup v2 hierarchy** (RHEL 9+, Ubuntu 22.04+, Debian 12+); v1's multi-hierarchy model is legacy. cgroup v2 collapses all controllers (`cpu`, `memory`, `io`, `pids`) into a single tree, which is what container runtimes drive today.
(Source: https://oneuptime.com/blog/post/2026-02-08-how-to-understand-docker-container-cgroups-in-depth/view — accessed 2026-07-01; Docker docs: https://docs.docker.com/engine/containers/resource_constraints/ — accessed 2026-07-01)

Docker/Podman `run` flags are thin wrappers over cgroup v2 files. The mapping every operator should know:

| Constraint | Docker/Podman flag | cgroup v2 file | Behavior |
|---|---|---|---|
| Memory hard cap | `--memory=512m` | `memory.max` | OOM-kill on breach |
| Memory soft cap | `--memory-reservation` | `memory.low`/`memory.high` **[APPROX — exact file depends on runtime version]** | reclaim pressure, burst allowed when host has free RAM |
| Mem + swap | `--memory-swap` | `memory.swap.max` (derived) | `--memory-swap` is total; swap allowance = swap − memory |
| CPU quota | `--cpus=2` | `cpu.max` (period+quota) | `--cpus` is shorthand that sets `--cpu-period`/`--cpu-quota` |
| CPU weight | `--cpu-shares` (0–1024, default 1024) | `cpu.weight` | proportional share **only under contention** |
| PID cap | `--pids-limit` | `pids.max` | fork-bomb defense |
| Block I/O | `--device-read-bps` etc. | `io.max`/`io.weight` | v1 `blkio.*` → v2 `io.*`; old tuning advice does not carry over |

Verify a live container by reading `/proc/<pid>/cgroup` → then `memory.max`, `cpu.max`, `pids.max`. If the value isn't in the file, the limit isn't enforced.
(Source: https://oneuptime.com/blog/post/2026-01-30-docker-container-resource-limits/view — accessed 2026-07-01; https://stackharbor.com/en/knowledge-base/docker-resource-limits/ — accessed 2026-07-01)

**Noisy-neighbor caveat:** `--cpu-shares`/`cpu.weight` is *proportional and only bites under contention* — it does NOT cap absolute CPU. For hard noisy-neighbor protection you need `--cpus` (absolute quota) plus `memory.max` plus `io.max`/`io.weight`. Weight-only configs let a single tenant saturate a quiet host.
(Source: Docker docs, resource_constraints — accessed 2026-07-01; Datadog Security Labs cgroups fundamentals: https://securitylabs.datadoghq.com/articles/container-security-fundamentals-part-4/ — accessed 2026-07-01)

### Network isolation

- **Per-tenant virtual networks** (per-tenant Docker networks / K8s NetworkPolicies) are the baseline: each tenant's processes run in an isolated network so one tenant can't reach another's services on the shared host.
- **VLANs** give L2 isolation but the 12-bit VLAN tag caps you at **4096 tenants** — a hard scalability ceiling. VXLAN/overlay networks are the usual escape from that limit. **[APPROX — VLAN limit is spec, VXLAN adoption for PaaS is general practice]**
- **Private/overlay networks** (encrypted per-tenant virtual networks) are the scalable option above the VLAN ceiling.
(Source: https://oneuptime.com/blog/post/2026-02-08-how-to-design-a-multi-tenant-docker-architecture/view — accessed 2026-07-01; https://workos.com/blog/tenant-isolation-in-multi-tenant-systems — accessed 2026-07-01)

### Filesystem isolation & per-tenant subdomains

- Filesystem isolation via mount namespaces + per-tenant volumes is standard; the recurring failure mode is the *host* filesystem leaking in through a runc escape (see §3), not the namespace itself.
- **Per-tenant subdomains** (`tenant1.example.com`, `tenant2.example.com`) routed independently at the ingress is the near-universal pattern; K8s multi-tenancy guidance treats ingress/hostname isolation as a first-class isolation dimension.
(Source: https://kubernetes.io/docs/concepts/security/multi-tenancy/ — accessed 2026-07-01; https://www.stakater.com/post/mastering-multi-tenancy-in-kubernetes-openshift-part-8 — accessed 2026-07-01)

---

## 2. Container isolation / sandboxing for UNTRUSTED workloads (2025–2026 status)

### gVisor (Google) — userspace kernel

**How it works:** gVisor re-implements the majority of the Linux syscall surface **in userspace** (the "Sentry" application kernel). Containers talk to gVisor's kernel, not the host kernel, so the host-kernel attack surface shrinks dramatically. It runs unprivileged.
(Source: https://gvisor.dev/docs/user_guide/production/ — accessed 2026-07-01)

**Performance overhead (official, by workload class):**
- CPU-bound (API servers, data pipelines): minimal overhead.
- I/O-heavy (databases): degraded — "File I/O is typically the most impacted performance characteristic."
- Network-heavy (load balancers): degraded — networking is "the second most-impacted."
gVisor's own guidance: *"While gVisor is able to sandbox any application, it should generally not be used to sandbox every application."* Off-GKE, run on **bare metal (not nested in a VM)** with the KVM platform for best performance.
(Source: https://gvisor.dev/docs/user_guide/production/ — accessed 2026-07-01)

**Adoption:** Powers **GKE Sandbox** and **Cloud Run** in production (Google's own serverless/multi-tenant surfaces). At Google Cloud Next '26, Google announced **GKE Agent Sandbox** built on gVisor kernel isolation, cited at **~300 sandboxes/second** for isolating AI-agent code — a strong 2026 signal that gVisor is Google's default untrusted-code boundary.
(Source: https://www.infoq.com/news/2026/05/gke-agent-sandbox-hypercluster/ — accessed 2026-07-01; https://gvisor.dev/docs/user_guide/production/ — accessed 2026-07-01)

**Note:** Security researchers point out gVisor is not a total boundary — Workload Identity, VPC-SC, and syscall-compat gaps still matter for defense-in-depth. **[Flagged: this is a security-vendor blog, not primary]** (Source: https://www.armosec.io/blog/sandboxing-ai-agents-gke-workload-identity/ — accessed 2026-07-01)

### Firecracker microVMs (AWS) — hardware-virtualized

**How it works:** A minimal KVM-based VMM (~50k LOC) giving each guest its own kernel behind a hardware-virtualization boundary. The **jailer** wraps the VMM in cgroup/namespace isolation + seccomp and drops privileges — defense-in-depth: HW virt for the guest *plus* process sandboxing for the VMM.
(Source: https://firecracker-microvm.github.io/ — accessed 2026-07-01; https://github.com/firecracker-microvm/firecracker — accessed 2026-07-01)

**Boot/density (official):** starts app code in **as little as 125 ms**, up to **150 microVMs/sec/host**, **< 5 MiB** memory overhead per microVM → high packing density.
(Source: https://aws.amazon.com/blogs/opensource/firecracker-open-source-secure-fast-microvm-serverless/ — accessed 2026-07-01)

**Adoption:** Built at AWS to power **Lambda** (one microVM per function invocation) and **Fargate** (Tasks now run on Firecracker on bare-metal EC2). **Fly.io** Machines: every `fly machine` is a Firecracker microVM with sub-second cold starts and persistent disks. Also cited powering **Bedrock AgentCore**. Third-party AI-sandbox platforms increasingly standardize on it.
(Source: https://fly.io/learn/firecracker-vm/ — accessed 2026-07-01; https://cloudrps.com/blog/firecracker-microvm-serverless-isolation/ — accessed 2026-07-01 — *secondary, but consistent with AWS primary*)

### Kata Containers — VM-per-container, OCI-native

**How it works:** Each workload (or pod) runs in a lightweight KVM VM with a **dedicated guest kernel**; hardware-enforced isolation via KVM. Fully **OCI-compatible** — drops into containerd/Kubernetes as a `RuntimeClass` with no image changes; the shimv2 architecture allows multiple containers per VM (pod model).
(Source: https://katacontainers.io/ — accessed 2026-07-01; https://github.com/kata-containers/kata-containers/blob/main/docs/design/architecture/README.md — accessed 2026-07-01)

**Adoption:** Baidu runs Kata in production (Function Computing, Cloud Container Instances, edge). AWS has published guidance on Kata for K8s workload isolation. **[NB: I could not confirm a specific Kata 3.x version/date from primary sources in this pass — treat the "3.x" line as UNVERIFIED.]**
(Source: https://aws.amazon.com/blogs/containers/enhancing-kubernetes-workload-isolation-and-security-using-kata-containers/ — accessed 2026-07-01; https://arunprasad86.medium.com/kata-containers-an-overview-7ed95dacfb7a — accessed 2026-07-01 — *secondary for the Baidu claim*)

**2026 trend:** Apple validated hypervisor-isolated containers (their `containerization` project), which the ecosystem reads as further mainstreaming of VM-per-container for untrusted code.
(Source: https://edera.dev/stories/apple-just-validated-hypervisor-isolated-containers-heres-what-that-means — accessed 2026-07-01 — *vendor blog, directional*)

### Comparison

| | Boundary strength | Perf overhead | Ops complexity | Realistic for small OSS PaaS 2026? |
|---|---|---|---|---|
| **Plain containers (runc)** | Shared host kernel — weakest | ~none | lowest | OK only for *trusted* tenants; not sufficient for untrusted (see §3) |
| **gVisor** | Strong (userspace kernel, no HW virt needed) | Low CPU / high on file+net I/O | Moderate — drop-in `runsc`, runs unprivileged, no nested-virt requirement | **Most realistic** untrusted-code option for a small PaaS; works on cheap VMs though best on bare metal |
| **Kata** | Very strong (per-container guest kernel + KVM) | VM-ish (higher than gVisor for most) | Moderate–high; needs **nested virt / bare metal** | Feasible if you control the host and have KVM; OCI-native helps |
| **Firecracker** | Very strong (microVM + jailer) | Low once booted; ~125ms cold start | **High** — you're building an orchestrator (Fly.io/Lambda-scale engineering) | Mostly "big-cloud / well-funded" territory; a small team adopts it via Fly.io-style platforms, not from scratch |

**Bottom line for a small OSS PaaS:** gVisor is the pragmatic sweet spot (strong boundary, drop-in runtime, no bare-metal mandate). Firecracker delivers Lambda-grade isolation but demands orchestrator-building effort that is "big-cloud only" unless you rent it via a platform. Kata sits between the two and is attractive if you already own KVM-capable hosts.

---

## 3. Is a shared kernel acceptable for untrusted tenants in 2026?

**Consensus: No — for genuinely untrusted multi-tenant workloads, plain shared-kernel containers are not a sufficient security boundary, and a VM/microVM/userspace-kernel boundary is now treated as table stakes.** The driver is a steady cadence of runc container-escape CVEs:

**2024 — "Leaky Vessels" (Snyk):** four CVEs in core container infra.
- **CVE-2024-21626** (runc): the headline flaw — a race in runc's handling of `/proc/self/fd` during init lets an attacker break the filesystem namespace and reach the **host root filesystem**, i.e. full host takeover. Explicitly called out as heightened-impact in multi-tenant clusters where tenants share nodes. **Patched in runc v1.1.12.**
- CVE-2024-23651/23652/23653 (BuildKit): patched in BuildKit v0.12.5.
(Source: https://www.wiz.io/blog/leaky-vessels-container-escape-vulnerabilities — accessed 2026-07-01; https://www.paloaltonetworks.com/blog/cloud-security/leaky-vessels-vulnerabilities-container-escape/ — accessed 2026-07-01)

**November 2025 — three fresh runc escapes** (disclosed **2025-11-05**):
- **CVE-2025-31133** — `maskedPaths` abuse: swap `/dev/null` for a symlink → runc mounts arbitrary host paths into the container. Affects all known versions.
- **CVE-2025-52565** — `/dev/console` bind-mount race/symlink → write access to critical procfs entries → breakout. Affects runc 1.0.0-rc3+.
- **CVE-2025-52881** — LSM bypass + arbitrary-write gadgets: redirect runc writes to `/proc` files (e.g. `/proc/sysrq-trigger`) via shared-mount races.
- **All fixed in runc 1.2.8, 1.3.3, 1.4.0-rc.3.** Mitigations stressed: **user namespaces / rootless**.
(Source: https://www.sysdig.com/blog/runc-container-escape-vulnerabilities — accessed 2026-07-01; https://orca.security/resources/blog/new-runc-vulnerabilities-allow-container-escape/ — accessed 2026-07-01)

**Expert framing (repeated across vendors):** *"never rely on containerization as a single security boundary, especially in multi-tenant environments"* — use defense-in-depth. Two 18-month cycles of host-escape CVEs in the default runtime is exactly why big clouds put Lambda in Firecracker and GKE untrusted pods in gVisor.
(Source: https://www.wiz.io/blog/leaky-vessels-container-escape-vulnerabilities — accessed 2026-07-01; https://www.wiz.io/academy/container-security/container-escape — accessed 2026-07-01)

**Practical read for 2026:** if tenants are *trusted* (your own teams, vetted customers), hardened shared-kernel containers + user namespaces + seccomp + patched runc are defensible. If tenants run *arbitrary/untrusted* code, the industry default is now a stronger boundary (gVisor / Kata / Firecracker) with containers as one layer of defense-in-depth, not the boundary.

---

## 4. Metering / billing / usage-based infrastructure (2025–2026)

### What to meter for a PaaS
CPU-seconds, memory-GB-hours, egress bandwidth, build-minutes, request counts, and storage-GB. Read live usage straight from cgroup counters (`memory.current`, `cpu.stat`) and emit events. Notably, **OpenMeter's Kubernetes collector can meter Pod CPU/memory/storage allocation directly** (and GPU/CPU/mem via Run:ai integration) — closest OSS to turnkey infra metering.
(Source: https://github.com/openmeterio/openmeter — accessed 2026-07-01; https://openmeter.io/ — accessed 2026-07-01)

### Open-source options
- **OpenMeter** (YC W23, OSS + managed): real-time metering + billing engine. Ingests **CloudEvents**, meters with SUM/COUNT/AVG/MIN/MAX aggregations, real-time queries, generates invoices with tiered/graduated/flat pricing. Has the K8s-workload collector noted above. Strong fit for infra metering.
(Source: https://github.com/openmeterio/openmeter — accessed 2026-07-01; https://openmeter.io/ — accessed 2026-07-01)
- **Lago** (getlago, OSS): usage-based billing + metering, explicitly pitches **"metering API calls, bandwidth, build minutes, or compute time and charging per-unit or per-tier,"** ingests up to **1M events/sec**, supports prepaid credits, allowances, consumption models.
(Source: https://github.com/getlago/lago — accessed 2026-07-01; https://getlago.com/platform/usage-metering — accessed 2026-07-01)

### Commercial / hosted
- **Stripe Billing meters** (v2 meter-events API): the legacy usage-records API was **removed in Stripe API version 2025-03-31.basil** — new integrations must use **billing meters**. Handles up to **200,000 usage events/sec** (livemode API ~1,000 events/sec, higher via meter-event streams). Supports usage-based, tiered, credit, hybrid pricing.
(Source: https://docs.stripe.com/api/billing/meter — accessed 2026-07-01; https://docs.stripe.com/billing/subscriptions/usage-based-legacy/migration-guide — accessed 2026-07-01)
- **Metronome** (now a Stripe product): purpose-built for the most complex usage-first billing — metering → rating → contract logic → invoices pushed to Stripe; multidimensional pricing, thousands of rates. For heavy/complex consumption models beyond vanilla Stripe meters.
(Source: https://docs.stripe.com/billing/how-metronome-works-with-stripe — accessed 2026-07-01)

### Recommended shape
Meter as an **event pipeline** (cgroup/runtime counters → CloudEvents → OpenMeter or Lago for aggregation/rating → Stripe meters for payment/invoicing). OpenMeter/Lago give you OSS metering + rating; Stripe handles money. Metronome only if pricing complexity explodes.

---

## Implication for Tetra

Tetra today orchestrates **Coolify** (which runs plain Docker/shared-kernel containers) behind a multi-tenant panel where multi-tenancy is stated as a hard requirement. The research says the isolation Tetra can rely on *right now* is only strong enough for **trusted tenants**: shared-kernel containers with patched runc (≥1.2.8/1.3.3 to close the Nov-2025 escapes), user namespaces, seccomp, and per-tenant cgroup v2 limits (`--cpus` + `memory.max` + `pids.max` + `io.max`, not weight-only) plus per-tenant Docker networks and subdomain routing. The moment Tetra hosts **untrusted tenant code**, a shared kernel is below the 2026 industry bar — the pragmatic upgrade path is a **gVisor (`runsc`) runtime class** under Coolify's Docker (strong boundary, drop-in, no bare-metal mandate), reserving Firecracker/Kata for if/when Tetra controls KVM-capable hosts. On billing, Tetra can meter directly from cgroup counters into **OpenMeter or Lago** (both OSS, both explicitly support compute/bandwidth/build-minute metering) and settle through **Stripe billing meters** — a realistic stack for a small platform without building metering from scratch. **[Flagged: whether Coolify exposes a runtime-class / `runsc` hook, and whether Tetra's hosts are bare-metal vs nested VMs, needs verification against the actual deployment before committing to gVisor.]**
