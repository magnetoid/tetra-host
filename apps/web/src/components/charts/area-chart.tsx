"use client"

import {
  Area,
  AreaChart as RechartsAreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export type AreaSeries = { key: string; label: string; color: string }
export type AreaPoint = { date: string; [key: string]: number | string }

/** Tremor-style stacked/overlaid area chart, themed for the dark console. */
export function AreaChart({
  data,
  series,
  valueFormatter = (value) => `${value}`,
  height = 240,
}: {
  data: AreaPoint[]
  series: AreaSeries[]
  valueFormatter?: (value: number) => string
  height?: number
}) {
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-dashed border-border bg-background text-sm text-zinc-500"
        style={{ height }}
      >
        No traffic data for this window.
      </div>
    )
  }

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsAreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`area-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(value: string) => (typeof value === "string" ? value.slice(5) : value)}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#27272a" }}
            minTickGap={16}
          />
          <YAxis
            tickFormatter={(value: number) => valueFormatter(value)}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip
            isAnimationActive={false}
            contentStyle={{
              background: "#09090b",
              border: "1px solid #27272a",
              borderRadius: 12,
              fontSize: 12,
            }}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={(value, name) => [valueFormatter(Number(value) || 0), name]}
          />
          {series.map((s) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              fill={`url(#area-${s.key})`}
              isAnimationActive={false}
            />
          ))}
        </RechartsAreaChart>
      </ResponsiveContainer>
    </div>
  )
}
