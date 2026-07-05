"use client"

import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
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

export type LineChartProps = {
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
  height?: number
  className?: string
  emptyMessage?: string
}

/** Theme-aware Tremor-style line chart (Recharts 3). */
export function LineChart({
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
  height = 240,
  className,
  emptyMessage = "No data for this window.",
}: LineChartProps) {
  const series = toSeries(categories, colors, categoryLabels)

  if (data.length === 0) {
    return <ChartEmpty message={emptyMessage} height={height} />
  }

  return (
    <div className={className}>
      {showLegend && series.length > 0 ? <ChartLegend series={series} className="mb-3" /> : null}
      <ResponsiveChart height={height}>
        {(width, h) => (
          <RechartsLineChart width={width} height={h} data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
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
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.key}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, stroke: s.color, fill: "var(--background)" }}
                isAnimationActive={false}
              />
            ))}
          </RechartsLineChart>
        )}
      </ResponsiveChart>
    </div>
  )
}
