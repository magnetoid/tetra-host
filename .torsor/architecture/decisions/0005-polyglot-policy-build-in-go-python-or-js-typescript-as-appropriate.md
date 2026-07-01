---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T01:20:55'
updated: '2026-07-02T01:20:55'
rules:
- id: tetra-polyglot-go-python-js
  description: 'Build each component in the language that fits: Python (backend/CLI),
    TypeScript/JS (console/edge), or Go (daemons, single-binary agents/reconcilers,
    perf-critical or Go-ecosystem-native tools). Don''t force one language where another
    fits better; don''t add a 4th language without a recorded decision.'
  severity: info
---

# ADR 0005: Polyglot policy: build in Go, Python, or JS/TypeScript as appropriate

## Context
The charter already says "use the right language for the job (Python + TypeScript today; Go or other languages where they fit)". As Tetra AI Cloud grows toward own-infra provisioning, agents/reconcilers, single-binary tooling, and performance-sensitive daemons, we want this stated as an explicit, enforceable rule so component language choice is a deliberate fit decision rather than defaulting to Python/TS everywhere or sprawling into many languages.

## Decision
Tetra AI Cloud is a deliberate polyglot built from three sanctioned languages, chosen per component by fit: (1) PYTHON — the FastAPI backend, provider services, domain/business logic, and the tetra CLI (default for panel/orchestration code). (2) JavaScript/TypeScript — the Next.js console and any browser/edge/Node surface. (3) Go — where it clearly fits: performance-critical or long-running daemons, single-static-binary agents/reconcilers (e.g. a cloud-init callback agent, a host-side reconciler for privileged ops, edge/proxy glue), and tools where the Go ecosystem is the reference client (e.g. Hetzner hcloud, Docker/containerd, Caddy plugins). Pick the language that fits the component; do NOT force Python/TS where Go is the better tool, and do NOT introduce a fourth language without recording a decision. Each language stays behind clean service/API boundaries so components remain independently testable and swappable.

## Consequences
Positive: right-tool-for-the-job performance and ecosystem fit (Go single binaries for host agents avoid shipping a Python runtime); keeps the stack intentional and reviewable. Trade-offs: more than one toolchain to build/test/CI; contributors need Go fluency for those components. Mitigation: confine Go to well-scoped daemons/agents/tools behind APIs, keep Python+TS as the primary surfaces, and require a recorded decision before adding any language beyond Go/Python/JS-TS.
