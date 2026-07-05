"use client"

import { useId } from "react"
import { Area, AreaChart } from "recharts"

import { ResponsiveChart } from "./responsive-chart"
import { resolveColors } from "./chart-utils"

export type SparkAreaChartProps = {
  data: Record<string, string | number>[]
  index: string
  categories: string[]
  colors?: string[]
  height?: number
  className?: string
}

/** Chromeless inline sparkline — no axes, grid, tooltip, or legend. */
export function SparkAreaChart({
  data,
  index,
  categories,
  colors,
  height = 48,
  className,
}: SparkAreaChartProps) {
  const gradientId = useId()
  const palette = resolveColors(categories.length, colors)

  if (data.length === 0) {
    return <div style={{ height }} className={className} aria-hidden />
  }

  return (
    <div className={className}>
      <ResponsiveChart height={height}>
        {(width, h) => (
          <AreaChart width={width} height={h} data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            {categories.map((key, i) => (
              <linearGradient key={key} id={`${gradientId}-${key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={palette[i]} stopOpacity={0.3} />
                <stop offset="100%" stopColor={palette[i]} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          {categories.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              // index is referenced for API symmetry with the full charts; sparks omit axes.
              name={index}
              stroke={palette[i]}
              strokeWidth={1.5}
              fill={`url(#${gradientId}-${key})`}
              dot={false}
              isAnimationActive={false}
            />
          ))}
          </AreaChart>
        )}
      </ResponsiveChart>
    </div>
  )
}
