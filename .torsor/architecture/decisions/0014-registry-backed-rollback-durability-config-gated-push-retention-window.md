---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-03T07:00:00'
updated: '2026-07-03T07:00:00'
rules:
- id: tetra-registry-best-effort-push
  rule: Registry push and retention pruning are best-effort side paths — a down or
    missing registry must never fail a deploy or flip a READY deployment to ERROR;
    with REGISTRY_URL empty the engine behaves exactly as before the registry existed
    (local-only images, no pruning).
- id: tetra-image-retention-protections
  rule: Image retention counts DISTINCT images (rollback rows re-point at old images
    and must not shrink the window), stands down entirely while any QUEUED/BUILDING
    row exists for the tenant+project, never deletes an image another tenant's rows
    reference (image names tetra-<project>:<sha> are only per-tenant unique), and
    deletes registry manifests by TAG only — never by digest, which would sever
    sibling tags sharing a manifest after a build-cache hit.
---

# ADR 0014: Registry-backed rollback durability — config-gated push + retention window

## Context
Instant rollback (Phase 1) pins a prior deployment's image and re-runs the stack — but the
image only existed in the host Docker daemon. Any local prune (including our own future
disk-discipline jobs on a box at ~85% disk) silently breaks rollback. The ratified roadmap
calls for pushing every build to a registry so rollback survives local image eviction, with
a retention policy.

## Decision
A new `app/services/registry.py` (`ImageRegistry`) — config-gated on `REGISTRY_URL`
(empty ⇒ disabled ⇒ exact pre-slice behavior), same injectable-async-runner pattern as
Builder/DockerEngine:

1. **Push on deploy:** every successful **non-preview** build is tagged
   `{REGISTRY_URL}/{image}` and pushed; the **registry-qualified ref** is what gets
   recorded on the Deployment (persisted while still BUILDING, so retention always sees
   which image an in-flight build owns) and put in the compose file. After a successful
   push the bare builder tag is untagged, so the qualified ref is the image's only local
   tag and retention's `rmi` actually reclaims disk. Push is best-effort: on failure the
   deploy continues with the local-only name and a ⚠ log line. Scheme-less
   `REGISTRY_URL` hosts follow docker's own rule: loopback ⇒ HTTP, anything else ⇒ HTTPS.
2. **Pull on rollback:** `_run_rollback` checks `docker image inspect`; a missing
   registry-qualified image is re-pulled from the registry. A missing **local-only** image
   fails fast with an honest error ("predates the registry" / "no registry is configured")
   instead of compose's confusing Docker Hub 404.
3. **Retention window:** after each successful deploy, images beyond the newest
   `REGISTRY_KEEP_IMAGES` (default 5) **distinct** images of that tenant+project's READY
   deployments are deleted locally (`docker rmi`) and untagged in the registry — by
   **tag**, never by digest (a digest DELETE would sever sibling tags sharing a manifest
   after a build-cache hit). Images pushed for deployments that later failed are cleaned
   up the same way. Protections: the whole cycle stands down while any QUEUED/BUILDING
   row exists for the project, and an image referenced by any other tenant is never
   deleted. Pruning is fully self-contained and swallows every failure — it can never
   flip a READY deployment to ERROR. Blob space is reclaimed by the registry's offline
   `garbage-collect --delete-untagged` (stop → GC in transient container → start;
   documented in `scripts/install-registry.sh`).

Prod runs a `registry:3` container bound to **127.0.0.1:5000 only** (never exposed; the
shared box's other local users are trusted admin-level today) with
`REGISTRY_STORAGE_DELETE_ENABLED=true`, installed idempotently by
`scripts/install-registry.sh`.

## Consequences
Rollback is now durable against local image pruning for all post-slice deployments, and the
rollback window is explicit and bounded (newest N distinct builds) instead of accidental.
Pre-registry deployments keep local-only refs and degrade with an honest error. Previews stay
local-only (ephemeral, never rolled back). The registry lives on the same disk today, so this
protects against *pruning*, not disk loss — moving the registry off-box (or to Harbor) is the
future hardening step. Surfaces need no changes: the image ref is transparent data in the
existing API/CLI/MCP/console fields. Adversarially reviewed before merge (4 dimensions,
28 agents, per-finding refutation): 8 distinct confirmed defects fixed — including two
high-severity wrong-deletes in retention (row-counted window collapsed by rollback rows;
digest-based deletion severing shared-manifest siblings) — each with a regression test.
