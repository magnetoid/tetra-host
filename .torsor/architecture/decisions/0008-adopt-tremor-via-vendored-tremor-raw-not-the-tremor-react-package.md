---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T05:20:11'
updated: '2026-07-02T05:20:11'
rules:
- id: tremor-vendor-raw-not-npm
  description: For console charts, vendor Tremor Raw components (github.com/tremorlabs/tremor)
    into src/components/tremor/, brand-tuned; do NOT install the @tremor/react npm
    package (needs React 18 + Recharts 2 + Tailwind v3, incompatible with this Next16/React19/Tailwind4/Recharts3
    console).
  severity: warn
---

# ADR 0008: Adopt Tremor via vendored Tremor Raw, not the @tremor/react package

## Context
ADR 0006 mandates Tremor for console data-viz. In practice the console is Next 16 / React 19 / Tailwind v4 (CSS-first, no tailwind.config) / Recharts 3. Attempting `pnpm add @tremor/react` (v3.18.7) surfaced hard incompatibilities: it requires react@^18 (peer conflict with React 19), pins its own recharts@2.15.4 (duplicating/clashing with the repo's Recharts 3), and expects Tailwind-v3 config-based color theming that doesn't exist under Tailwind v4. It was removed.

## Decision
Honor ADR 0006's "use Tremor" rule via **Tremor Raw** — the copy-paste components from github.com/tremorlabs/tremor (MIT), which are Recharts-3 / React-19 / Tailwind-v4 native and depend only on tailwind-variants + clsx + tailwind-merge (already installed). Vendor the needed components verbatim into apps/web/src/components/tremor/ (utils = cx+focusRing; bar-list, and future chart/category components), brand-tuning colors to the Tetra palette (violet/cyan) instead of Tremor's default blue + `dark:` classes (the console is dark-only via CSS tokens, not a `.dark` class). Do NOT install the `@tremor/react` npm package. The existing Recharts-based charts (components/charts/*) may remain and/or be migrated toward the vendored Tremor components over time.

## Consequences
Positive: real Tremor components that work on this exact stack, owned in-repo (themeable, no version-lock, no broken peer deps). Trade-off: vendored components are hand-maintained (upstream fixes must be pulled manually) and each needs brand-tuning; charting is briefly mixed (Recharts charts + vendored Tremor BarList) until consolidated. First use: the /apps/[project]/compute panel.
