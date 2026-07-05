"use client"

import {
  Bar,
  CartesianGrid,
  BarChart as RechartsBarChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ResponsiveChart } from "./responsive-chart"
import {
  axisTick,
  chartGrid,
  ChartEmpty,
  ChartLegend,
  toSeries,
  tooltipLabelStyle,
  tooltipStyle,
} from "./chart-utils"

export type BarChartProps = {
  data: Record<string, string | number>[]
  index: string
  categories: string[]
  colors?: string[]
  categoryLabels?: Record<string, string>
  valueFormatter?: (value: number) => string
  xValueFormatter?: (value: string) => string
  showLegend?: boolean
  showGrid?: boolean
  showYAxis?: boolean
  stacked?: boolean
  height?: number
  className?: string
  emptyMessage?: string
}

/** Theme-aware Tremor-style bar chart (Recharts 3). Grouped by default, stackable. */
export function BarChart({
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
}: BarChartProps) {
  const series = toSeries(categories, colors, categoryLabels)

  if (data.length === 0) {
    return <ChartEmpty message={emptyMessage} height={height} />
  }

  return (
    <div className={className}>
      {showLegend && series.length > 0 ? <ChartLegend series={series} className="mb-3" /> : null}
      <ResponsiveChart height={height}>
        {(width, h) => (
          <RechartsBarChart width={width} height={h} data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
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
              cursor={{ fill: "var(--chart-cursor)", opacity: 0.25 }}
              contentStyle={tooltipStyle}
              labelStyle={tooltipLabelStyle}
              itemStyle={{ color: "var(--foreground)" }}
              formatter={(value, name) => [
                valueFormatter(Number(value) || 0),
                categoryLabels?.[String(name)] ?? name,
              ]}
            />
            {series.map((s, i) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.key}
                stackId={stacked ? "a" : undefined}
                fill={s.color}
                radius={stacked && i < series.length - 1 ? 0 : [4, 4, 0, 0]}
                maxBarSize={48}
                isAnimationActive={false}
              />
            ))}
          </RechartsBarChart>
        )}
      </ResponsiveChart>
    </div>
  )
}
