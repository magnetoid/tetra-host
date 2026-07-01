---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-30T15:48:45'
updated: '2026-06-30T15:48:45'
rules:
- id: console-shadcn-tremor
  applies_to: apps/web
  rule: Build console UI with shadcn/ui (components, cn/Tailwind) + Tremor (charts,
    meters, dashboard widgets); avoid ad-hoc/bespoke components and migrate custom
    ui/* primitives toward shadcn/ui.
---

# ADR 0002: Console UI styled with shadcn/ui + Tremor

## Context
Tetra Host's console (apps/web, Next.js 16 / React 19 / Tailwind v4) currently mixes custom primitives (ui/Button, ui/Card) with Tremor/Recharts for data viz and Font Awesome for icons. The team wants a single, consistent, premium component/styling standard across the console so new surfaces (plans, tenants, usage meters, dashboards, future provider modules) look cohesive and modern without reinventing components.

## Decision
Build the console UI with shadcn/ui (Radix-based components + the `cn` utility / Tailwind styling) for general components and layout, and Tremor for data-visualization and dashboard widgets (charts, meters, KPI cards, usage/quota displays). Prefer composing these libraries over hand-rolling ad-hoc components; migrate existing custom ui/* primitives toward shadcn/ui equivalents incrementally as surfaces are touched. Font Awesome remains the icon set (prior decision) unless revisited.

## Consequences
New/edited console components should use shadcn/ui + Tremor rather than bespoke markup; the existing custom ui/Button + ui/Card become migration targets. Data/metric surfaces (usage meters, dashboards) use Tremor. Keeps the premium, cutting-edge UX bar while reducing component drift. Requires adding shadcn/ui scaffolding (components.json + the cn util) if not already present.
