---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-03T04:30:00'
updated: '2026-07-03T04:30:00'
rules:
- id: tetra-ai-heuristic-first
  rule: AI-assisted features must degrade to a deterministic, offline path when no API
    key is configured (ANTHROPIC_API_KEY empty => heuristic only), and LLM enrichment
    must be best-effort — any error falls back to the deterministic result and never
    fails the endpoint.
- id: tetra-ai-untrusted-input-fenced
  rule: Attacker-influenceable content (build logs, recorded errors, user data) sent
    to an LLM must be fenced as untrusted data inside a per-request random-nonce marker
    with trusted instructions in the system prompt and the response constrained to a
    JSON schema; never interpolate such content outside the fence as trusted metadata.
---

# ADR 0013: AI build-failure diagnosis — heuristic-first, optional Anthropic enrichment, untrusted logs

## Context
Phase 4 of the Tetra AI Cloud program (ADR 0004) calls for AI-assisted deploy/log debugging as a fast-follow to the MCP surface (ADR 0012). The platform needs to explain *why* a build failed and suggest fixes — the Vercel "AI fix this build" bar. Constraints: it must work on open-source installs with no API key (config-gating pattern, like Umami/GlitchTip per ADR 0011); build logs are attacker-influenceable (a tenant controls their repo's build output), so any LLM call is a prompt-injection surface; and the CLI keeps its no-new-dependencies rule while the backend may take an optional dep.

## Decision
`tetra ai explain <deployment>` (and `GET /api/v1/deploys/{id}/explain`, and the MCP `explain_deployment` read tool) diagnose a deployment via two layers in `app/services/build_diagnostics.py`:
1. A **pure, offline heuristic analyzer** — a taxonomy of known Tetra Engine failure signatures (no-buildpack, dependency conflicts, OOM, port-binding, git-auth, Dockerfile, unknown) → a structured `Diagnosis`. Always available, deterministic, zero-config; this is the golden path.
2. An **optional Anthropic Messages API enricher**, gated on `ANTHROPIC_API_KEY` (default model `claude-opus-4-8`). It runs only for *failed* deployments, lazy-imports the SDK, runs the blocking call in a worker thread, and is **best-effort** — any failure (missing key/SDK, API error, non-object JSON) falls back to the heuristic so the endpoint never fails on the AI path.

Prompt-injection posture: the build log AND the recorded error are treated as untrusted data, fenced together inside a **per-request random-nonce marker** (so log content can't forge the closing fence), with the trusted instructions in the system prompt and the response constrained to a JSON schema via `output_config.format`. Only the log tail (12K chars) is sent. Full three-surface parity (API + CLI + MCP + console "Explain" button on failed deployments).

## Consequences
The Metrics/Errors-style config-gating extends to AI: installs without a key still get useful, deterministic diagnoses; installs with a key get richer ones at no reliability cost. The heuristic taxonomy is the durable core and must be kept current as new failure modes appear. Because logs are untrusted, the fenced-nonce + system-prompt + JSON-schema pattern is now the required shape for any future feature that sends tenant-influenceable content to an LLM (rule `tetra-ai-untrusted-input-fenced`). The AI path is content-steering-resistant but not immune — the JSON schema bounds structure, not the wording of the diagnosis fields; downstream surfaces (CLI, MCP) render those fields, so they remain data, never executed. Adversarially reviewed (correctness + security + parity, each finding independently verified) before merge; six confirmed findings fixed.
