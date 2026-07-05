// Shared chrome for the vendored Tremor charts. Every color is a CSS-var string so
// Recharts re-resolves it on a light/dark flip — no JS re-render needed. Adapted for
// Recharts 3 + Tailwind v4 (the @tremor/react npm package targets Recharts 2 / TW v3).
import { cx } from "./utils"

/** Categorical series palette, brand-first (violet, cyan, emerald, amber, pink, blue). */
export const chartPalette = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
] as const

export const chartGrid = "var(--chart-grid)"
export const chartAxis = "var(--chart-axis)"
export const chartCursor = "var(--chart-cursor)"

/** Recharts tick style for both axes. */
export const axisTick = { fill: chartAxis, fontSize: 11 } as const

/** Recharts `contentStyle`/`labelStyle` for tooltips, themed to the popover surface. */
export const tooltipStyle = {
  background: "var(--chart-tooltip-bg)",
  border: "1px solid var(--chart-tooltip-border)",
  borderRadius: 12,
  fontSize: 12,
  color: "var(--foreground)",
  boxShadow: "0 8px 24px rgb(0 0 0 / 0.24)",
} as const

export const tooltipLabelStyle = { color: "var(--muted-foreground)", marginBottom: 2 } as const

/** Resolve one color per category, cycling the palette when none is supplied. */
export function resolveColors(count: number, colors?: readonly string[]): string[] {
  const source = colors && colors.length > 0 ? colors : chartPalette
  return Array.from({ length: count }, (_, i) => source[i % source.length])
}

export type ChartSeries = { key: string; color: string; label: string }

/** Zip categories → {key, color, label} using optional friendly labels. */
export function toSeries(
  categories: readonly string[],
  colors?: readonly string[],
  labels?: Record<string, string>,
): ChartSeries[] {
  const resolved = resolveColors(categories.length, colors)
  return categories.map((key, i) => ({
    key,
    color: resolved[i],
    label: labels?.[key] ?? key,
  }))
}

/** A compact, theme-aware legend rendered above/below charts (not Recharts' own). */
export function ChartLegend({
  series,
  className,
}: {
  series: ChartSeries[]
  className?: string
}) {
  return (
    <div className={cx("flex flex-wrap items-center gap-x-4 gap-y-1", className)}>
      {series.map((s) => (
        <div key={s.key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-2 shrink-0 rounded-full" style={{ background: s.color }} />
          {s.label}
        </div>
      ))}
    </div>
  )
}

/** Shared empty-state for charts with no data. */
export function ChartEmpty({ message, height }: { message: string; height: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-xl border border-dashed border-border bg-background text-sm text-muted-foreground"
      style={{ height }}
    >
      {message}
    </div>
  )
}
