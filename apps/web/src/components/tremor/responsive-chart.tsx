"use client"

import { useEffect, useRef, useState, type ReactElement } from "react"

/**
 * Self-measured chart sizing. Recharts' own ResponsiveContainer latches a width of 0
 * on first mount under React 19 StrictMode (the dev double-invoke drops the initial
 * ResizeObserver reading), leaving charts blank. We measure the container width
 * ourselves and hand it to the chart as an explicit number.
 *
 * `children` is a render function `(width, height) => <RechartsChart .../>`. Before the
 * first measurement — and in non-layout environments like jsdom — we fall back to a
 * nominal width so the chart still mounts (and tests can assert on it).
 */
export function ResponsiveChart({
  height,
  children,
}: {
  height: number
  children: (width: number, height: number) => ReactElement
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = ref.current
    // Guard ResizeObserver: it's absent in jsdom (tests) — the fallback width covers it.
    if (!el || typeof ResizeObserver === "undefined") return
    const measure = () => setWidth(el.clientWidth)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <div ref={ref} style={{ width: "100%", height }}>
      {children(width || 600, height)}
    </div>
  )
}
