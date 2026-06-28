"use client"

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts"

export type DonutSlice = { name: string; value: number; color: string }

/** Tremor-style donut with a centered total, themed for the dark console. */
export function DonutChart({
  data,
  centerLabel,
  centerSublabel,
}: {
  data: DonutSlice[]
  centerLabel?: string | number
  centerSublabel?: string
}) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0)
  const slices = total > 0 ? data : [{ name: "none", value: 1, color: "#27272a" }]

  return (
    <div className="relative h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
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
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-2xl font-semibold tracking-tight">{centerLabel ?? total}</div>
        {centerSublabel ? <div className="text-xs text-zinc-500">{centerSublabel}</div> : null}
      </div>
    </div>
  )
}

export function ChartLegend({ data }: { data: DonutSlice[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-400">
      {data.map((slice) => (
        <div key={slice.name} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: slice.color }} />
          {slice.name}
          <span className="text-zinc-600">{slice.value}</span>
        </div>
      ))}
    </div>
  )
}
