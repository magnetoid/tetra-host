"use client"

import { Cell, Pie, PieChart, Tooltip } from "recharts"

import { ResponsiveChart } from "./responsive-chart"
import { cx } from "./utils"
import { resolveColors, tooltipLabelStyle, tooltipStyle } from "./chart-utils"

export type DonutDatum = { name: string; value: number }

export type DonutChartProps = {
  data: DonutDatum[]
  /** One color per datum (by index); defaults to the categorical palette. */
  colors?: string[]
  valueFormatter?: (value: number) => string
  centerValue?: string | number
  centerLabel?: string
  height?: number
  className?: string
}

/** Theme-aware Tremor-style donut with an optional centered total (Recharts 3). */
export function DonutChart({
  data,
  colors,
  valueFormatter = (value) => `${value}`,
  centerValue,
  centerLabel,
  height = 160,
  className,
}: DonutChartProps) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0)
  const palette = resolveColors(data.length, colors)
  const slices =
    total > 0
      ? data.map((slice, i) => ({ ...slice, color: palette[i] }))
      : [{ name: "none", value: 1, color: "var(--chart-grid)" }]

  return (
    <div className={cx("relative w-full", className)} style={{ height }}>
      <ResponsiveChart height={height}>
        {(width, h) => (
          <PieChart width={width} height={h}>
          <Pie
            data={slices}
            dataKey="value"
            nameKey="name"
            innerRadius="68%"
            outerRadius="100%"
            paddingAngle={total > 0 ? 2 : 0}
            stroke="none"
            isAnimationActive={false}
          >
            {slices.map((slice) => (
              <Cell key={slice.name} fill={slice.color} />
            ))}
          </Pie>
          {total > 0 ? (
            <Tooltip
              isAnimationActive={false}
              contentStyle={tooltipStyle}
              labelStyle={tooltipLabelStyle}
              itemStyle={{ color: "var(--foreground)" }}
              formatter={(value, name) => [valueFormatter(Number(value) || 0), name]}
            />
          ) : null}
          </PieChart>
        )}
      </ResponsiveChart>
      {centerValue !== undefined || centerLabel ? (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          {centerValue !== undefined ? (
            <div className="font-mono text-2xl font-semibold tracking-tight tabular-nums">
              {centerValue}
            </div>
          ) : null}
          {centerLabel ? <div className="text-xs text-muted-foreground">{centerLabel}</div> : null}
        </div>
      ) : null}
    </div>
  )
}

/** Legend for donut data: name + mono value swatch rows. */
export function DonutLegend({
  data,
  colors,
  valueFormatter = (value) => `${value}`,
  className,
}: {
  data: DonutDatum[]
  colors?: string[]
  valueFormatter?: (value: number) => string
  className?: string
}) {
  const palette = resolveColors(data.length, colors)
  return (
    <div className={cx("space-y-1.5", className)}>
      {data.map((slice, i) => (
        <div key={slice.name} className="flex items-center gap-2 text-sm">
          <span
            className="size-2 shrink-0 rounded-full"
            style={{ background: palette[i] }}
          />
          <span className="text-muted-foreground">{slice.name}</span>
          <span className="ml-auto font-mono tabular-nums text-foreground">
            {valueFormatter(slice.value)}
          </span>
        </div>
      ))}
    </div>
  )
}
