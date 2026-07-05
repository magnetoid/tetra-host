"use client"

import { useId } from "react"
import {
  Area,
  CartesianGrid,
  AreaChart as RechartsAreaChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ResponsiveChart } from "./responsive-chart"
import {
  axisTick,
  chartCursor,
  chartGrid,
  ChartEmpty,
  ChartLegend,
  toSeries,
  tooltipLabelStyle,
  tooltipStyle,
} from "./chart-utils"

export type AreaChartProps = {
  data: Record<string, string | number>[]
  /** Key on each datum for the x-axis (e.g. "date"). */
  index: string
  /** Keys on each datum to draw as series. */
  categories: string[]
  colors?: string[]
  categoryLabels?: Record<string, string>
  valueFormatter?: (value: number) => string
  /** Format x-axis tick labels (e.g. trim a date's year). */
  xValueFormatter?: (value: string) => string
  showLegend?: boolean
  showGrid?: boolean
  showYAxis?: boolean
  stacked?: boolean
  height?: number
  className?: string
  emptyMessage?: string
}

/** Theme-aware Tremor-style area chart (Recharts 3). Colors resolve from CSS vars. */
export function AreaChart({
  data,
  index,
  categories,
  colors,
  categoryLabels,
  valueFormatter = (value) => `${value}`,
  xValueFormatter,
  showLegend = true,
  showGrid = true,
  showYAxis = true,
  stacked = false,
  height = 240,
  className,
  emptyMessage = "No data for this window.",
}: AreaChartProps) {
  const gradientId = useId()
  const series = toSeries(categories, colors, categoryLabels)

  if (data.length === 0) {
    return <ChartEmpty message={emptyMessage} height={height} />
  }

  return (
    <div className={className}>
      {showLegend && series.length > 0 ? <ChartLegend series={series} className="mb-3" /> : null}
      {/* Explicit numeric height on ResponsiveContainer — height="100%" fails to render
          the child chart under React 19 + Recharts 3 (container sizes, chart never mounts). */}
      <ResponsiveChart height={height}>
        {(width, h) => (
          <RechartsAreaChart width={width} height={h} data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              {series.map((s) => (
                <linearGradient
                  key={s.key}
                  id={`${gradientId}-${s.key}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor={s.color} stopOpacity={0.32} />
                  <stop offset="100%" stopColor={s.color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            {showGrid ? (
              <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} vertical={false} />
            ) : null}
            <XAxis
              dataKey={index}
              tickFormatter={xValueFormatter}
              tick={axisTick}
              tickLine={false}
              axisLine={{ stroke: chartGrid }}
              minTickGap={16}
            />
            {showYAxis ? (
              <YAxis
                tickFormatter={(value: number) => valueFormatter(value)}
                tick={axisTick}
                tickLine={false}
                axisLine={false}
                width={44}
              />
            ) : null}
            <Tooltip
              isAnimationActive={false}
              cursor={{ stroke: chartCursor, strokeWidth: 1 }}
              contentStyle={tooltipStyle}
              labelStyle={tooltipLabelStyle}
              itemStyle={{ color: "var(--foreground)" }}
              formatter={(value, name) => [
                valueFormatter(Number(value) || 0),
                categoryLabels?.[String(name)] ?? name,
              ]}
            />
            {series.map((s) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.key}
                stackId={stacked ? "a" : undefined}
                stroke={s.color}
                strokeWidth={2}
                fill={`url(#${gradientId}-${s.key})`}
                activeDot={{ r: 3, stroke: s.color, fill: "var(--background)" }}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </RechartsAreaChart>
        )}
      </ResponsiveChart>
    </div>
  )
}
