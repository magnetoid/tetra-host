# Console redesign — shadcn + Tremor, theme-aware

**Date:** 2026-07-05
**Surface:** `apps/web` (Next.js 16 / React 19 console)
**Status:** approved direction ("start"), building Phase 0 + 1

## Goal

Redesign the entire `apps/web` console on a shared, theme-aware design kit built from
shadcn/ui primitives and a vendored **Tremor** chart set. Data legibility is the hero;
the visual identity echoes the product's CLI parity (`tetra` CLI ↔ dashboard ↔ MCP).

## Decisions

- **Scope is decomposed into phases**, each independently shippable, all consuming one kit.
  Build Phase 0 (foundation) + Phase 1 (shell + dashboard) first; later clusters follow as
  their own specs.
- **Charts:** vendor the full Tremor chart set into `src/components/tremor/`, adapted to
  Recharts 3.9 (follow the proven `charts/area-chart.tsx` patterns) and made theme-aware via
  CSS-variable tokens. Replace the hand-rolled `charts/*` components and re-point consumers.
- **Theme:** theme-aware through semantic tokens (`bg-card`, `text-muted-foreground`,
  `border-border`, new chart/status tokens). New/rebuilt surfaces must not add fixed-zinc
  utilities. The legacy `[data-theme="light"]` zinc-override block in `globals.css` stays for
  now (older pages still lean on it) and shrinks as later phases migrate.
- **Type: keep ADR-0003** — Space Grotesk (display), Inter (body), JetBrains Mono (data).
  *Changed from an earlier Geist proposal:* the brand is ratified and JetBrains Mono already
  provides the mono-data "CLI echo". No font churn.
- **Signature:** a **status spine** — a thin terminal-style provider-health strip under the
  topbar — plus mono treatment of every machine value (counts, IDs, IPs, deploy hashes).

## Aesthetic direction

Operator's console that looks like the CLI it mirrors. Near-black canvas, violet (`#7c3aed`)
as the single brand accent, cyan (`#22d3ee`) reserved for *live/active* states. Status colors
(emerald/amber/red) stay muted until they carry signal. Hairline borders, calm surfaces,
generous whitespace. Boldness spent only on the status spine + mono data.

## Phase 0 — Foundation (the shared kit)

1. **Tokens** (`globals.css`): add theme-aware chart tokens (`--chart-grid`, `--chart-axis`,
   `--chart-cursor`, `--chart-tooltip-bg`, `--chart-tooltip-border`) and a categorical chart
   palette; add status tokens (`--status-ok`, `--status-warn`, `--status-err`, `--status-live`).
   Wire all into `@theme inline`. Define both dark (`:root`) and `[data-theme="light"]` values.
2. **Tremor chart set** in `src/components/tremor/`: `AreaChart`, `BarChart`, `LineChart`,
   `DonutChart`, `BarList` (exists), `SparkAreaChart`, plus a shared `chart-utils.ts`
   (palette, theme-aware axis/grid/tooltip config). Recharts-3 native, no hardcoded hex.
3. **shadcn primitives** in `src/components/ui/`: add `Table`, `Tabs`, `Tooltip`, `Skeleton`;
   confirm `Card`/`Badge`/`Button` render from semantic tokens.

## Phase 1 — Shell + Dashboard

1. **`app-shell`**: sidebar (brand, tenant/env context, nav), topbar (breadcrumb + user menu),
   and the **status spine** strip. Theme-aware; mono for machine values.
2. **`/dashboard`**: page header → status spine → stat row (mono values) → Traffic
   (Tremor `AreaChart`) + Provider health (Tremor `DonutChart`) → Resource mix (Tremor
   `BarList`) + Recent deploys. All theme-aware, consuming the new kit.

## Later phases (each its own spec)

Deploy console (projects/apps/deploys) → DNS/domains → mail → billing & tenancy
(plans/usage/tenants) → admin (admin/super-admin/account).

## Acceptance

- `pnpm web:check` (lint + typecheck + vitest) green.
- Dashboard renders correctly in both dark and light (`data-theme`), no hardcoded-hex chart
  breakage in light mode.
- New Tremor charts replace hand-rolled ones with consumers re-pointed and tests updated.
- No new fixed-zinc utilities in rebuilt surfaces.
