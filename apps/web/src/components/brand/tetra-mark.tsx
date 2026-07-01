"use client"

import { useEffect, useRef } from "react"

/**
 * Tetra AI Cloud signature — a rotating wireframe tetrahedron rendered on canvas.
 * Its four vertices stand for the four provider planes the platform orchestrates
 * (apps / mail / DNS / edge). Honors prefers-reduced-motion (renders a static frame).
 */
export function TetraMark({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    let raf = 0
    let width = 0
    let height = 0

    // regular tetrahedron: 4 vertices, 6 edges
    const V: number[][] = [
      [1, 1, 1],
      [1, -1, -1],
      [-1, 1, -1],
      [-1, -1, 1],
    ]
    const E: number[][] = [
      [0, 1],
      [0, 2],
      [0, 3],
      [1, 2],
      [1, 3],
      [2, 3],
    ]

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const rect = canvas.getBoundingClientRect()
      width = rect.width
      height = rect.height
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const rot = (p: number[], ax: number, ay: number): number[] => {
      const [x, y, z] = p
      const cy = Math.cos(ay)
      const sy = Math.sin(ay)
      const x1 = x * cy - z * sy
      const z1 = x * sy + z * cy
      const cx = Math.cos(ax)
      const sx = Math.sin(ax)
      const y1 = y * cx - z1 * sx
      const z2 = y * sx + z1 * cx
      return [x1, y1, z2]
    }

    const project = (p: number[]): number[] => {
      const scale = Math.min(width, height) * 0.32
      const dist = 4.2
      const f = dist / (dist - p[2] * 0.9)
      return [width / 2 + p[0] * scale * f, height / 2 + p[1] * scale * f, p[2]]
    }

    let t = 0.7
    const frame = () => {
      ctx.clearRect(0, 0, width, height)
      const ay = t * 0.5
      const ax = Math.sin(t * 0.32) * 0.5 + 0.4
      const pts = V.map((v) => project(rot(v, ax, ay)))

      ctx.lineWidth = 1.4
      ctx.lineCap = "round"
      for (const [a, b] of E) {
        const pa = pts[a]
        const pb = pts[b]
        const g = ctx.createLinearGradient(pa[0], pa[1], pb[0], pb[1])
        g.addColorStop(0, "rgba(124,58,237,0.95)")
        g.addColorStop(1, "rgba(34,211,238,0.9)")
        ctx.strokeStyle = g
        ctx.shadowColor = "rgba(124,58,237,0.55)"
        ctx.shadowBlur = 14
        ctx.beginPath()
        ctx.moveTo(pa[0], pa[1])
        ctx.lineTo(pb[0], pb[1])
        ctx.stroke()
      }

      for (const p of pts) {
        const front = p[2] > 0
        ctx.fillStyle = front ? "rgba(196,181,253,1)" : "rgba(34,211,238,0.95)"
        ctx.shadowColor = ctx.fillStyle
        ctx.shadowBlur = 18
        ctx.beginPath()
        ctx.arc(p[0], p[1], front ? 4.6 : 3.2, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.shadowBlur = 0

      if (!reduce) {
        t += 0.006
        raf = requestAnimationFrame(frame)
      }
    }

    let resizeTimer: ReturnType<typeof setTimeout>
    const onResize = () => {
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => {
        resize()
        if (reduce) frame()
      }, 120)
    }

    resize()
    frame()
    window.addEventListener("resize", onResize)
    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(resizeTimer)
      window.removeEventListener("resize", onResize)
    }
  }, [])

  return <canvas ref={ref} className={className} aria-hidden="true" />
}
