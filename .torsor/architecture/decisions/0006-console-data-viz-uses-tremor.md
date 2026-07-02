---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T02:27:33'
updated: '2026-07-02T02:27:33'
rules:
- id: console-tremor-dataviz
  description: In apps/web, build charts, KPI/metric cards, usage meters, and analytics
    displays with Tremor components (themed to the Tetra palette); don't hand-roll
    bespoke chart/metric UI where a Tremor equivalent exists.
  severity: info
---

# ADR 0006: Console data-viz uses Tremor

## Context
ADR 0002 already established the console (apps/web) is styled with shadcn/ui + Tremor. The user wants this made an explicit, enforceable torsor rule so dashboard/data-visualization UI consistently uses Tremor rather than ad-hoc chart/metric components.

## Decision
The Next.js console (apps/web) uses Tremor as its data-visualization / dashboard component layer — charts, KPI/metric cards, usage meters, and analytics displays are built with Tremor components (composed with shadcn/ui primitives + Tailwind v4 tokens and the Tetra brand palette per ADR 0003). This complements, and does not replace, shadcn/ui for general UI (forms, dialogs, nav) per ADR 0002. Do not hand-roll bespoke chart/metric components where a Tremor equivalent exists.

## Consequences
Positive: consistent, premium dashboard visuals with less bespoke code; aligns with ADR 0002. Trade-off: Tremor's styling must be reconciled with the Tetra palette/tokens (theme Tremor via CSS variables). Backend (FastAPI/Jinja panel) is unaffected — this rule scopes to apps/web.
