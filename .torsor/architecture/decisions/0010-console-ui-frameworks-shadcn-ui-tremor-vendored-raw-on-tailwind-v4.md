---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T21:07:46'
updated: '2026-07-02T21:07:46'
rules:
- id: console-ui-shadcn-tremor-only
  description: apps/web UI is built with shadcn/ui-style primitives (general components)
    + vendored Tremor Raw (data-viz) on Tailwind v4 tokens; do not introduce other
    CSS/UI frameworks or the @tremor/react npm package without a recorded decision.
  severity: warn
---

# ADR 0010: Console UI frameworks: shadcn/ui + Tremor (vendored Raw) on Tailwind v4

## Context
User directive consolidating ADR 0002 (shadcn/ui + Tremor styling), ADR 0006 (Tremor data-viz), and ADR 0008 (vendored Tremor Raw, not @tremor/react): make the console's UI framework standard a single explicit, enforceable rule.

## Decision
The console (apps/web) standardizes on two component frameworks over Tailwind v4: (1) shadcn/ui-style primitives (Radix patterns + Tailwind tokens, composed via cn/tailwind-variants) for general UI — forms, buttons, cards, dialogs, nav, tables; (2) Tremor for data-visualization — charts, KPI/metric cards, usage meters, bar lists — adopted by vendoring Tremor Raw components into src/components/tremor/ brand-tuned to the Tetra palette (never the @tremor/react npm package, per ADR 0008). Tailwind v4 CSS-first tokens (globals.css @theme) are the single theming source; no other CSS/UI framework (Bootstrap, MUI, Chakra, styled-components, etc.) may be introduced without a recorded decision.

## Consequences
Positive: one coherent, premium look; predictable component vocabulary; vendored Tremor stays compatible with React 19/Tailwind v4. Trade-off: shadcn/Tremor components are owned in-repo and hand-maintained. Existing bespoke primitives migrate incrementally (ADR 0002 stance).
