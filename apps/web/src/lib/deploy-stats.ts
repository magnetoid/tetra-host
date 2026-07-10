/**
 * Deployment statistics — derived purely from a project's deployment history so the
 * Metrics tab has real, always-available numbers (unlike web analytics, which needs
 * Umami wired). Pure + testable: pass `now` in tests to pin the activity window.
 */

import type { ProjectDeploymentRecord } from "@/lib/types"

export type DeployOutcome = "succeeded" | "failed" | "running"

export interface DeployStats {
  total: number
  succeeded: number
  failed: number
  running: number
  /** Success rate over *finished* deploys (succeeded / (succeeded + failed)), 0–100. */
  successRate: number
  /** ISO timestamp of the most recent deploy, or "" when there are none. */
  lastDeployAt: string
  /** Deploys per calendar day across the activity window (oldest → newest). */
  perDay: { date: string; deploys: number }[]
  /** For a status donut. Zero-value slices are kept so the legend is stable. */
  statusBreakdown: { name: string; value: number }[]
}

export function classifyDeploy(status: string): DeployOutcome {
  const s = (status || "").toLowerCase()
  if (/(fail|error|cancel|crash|timeout)/.test(s)) return "failed"
  if (/(queue|build|progress|pending|deploying|starting)/.test(s)) return "running"
  if (/(finish|success|done|ready|complete|live|healthy|deployed)/.test(s)) return "succeeded"
  return "running" // unknown → neutral (excluded from the success rate)
}

function dayKey(iso: string): string {
  // The date part of an ISO timestamp; falls back to the raw first 10 chars.
  return (iso || "").slice(0, 10)
}

export function computeDeployStats(
  deployments: ProjectDeploymentRecord[],
  opts: { now?: Date; windowDays?: number } = {},
): DeployStats {
  const windowDays = opts.windowDays ?? 14
  let succeeded = 0
  let failed = 0
  let running = 0
  let lastDeployAt = ""
  const perDayCount = new Map<string, number>()

  for (const d of deployments) {
    const outcome = classifyDeploy(d.status)
    if (outcome === "succeeded") succeeded++
    else if (outcome === "failed") failed++
    else running++

    if (d.created_at && d.created_at > lastDeployAt) lastDeployAt = d.created_at

    const key = dayKey(d.created_at)
    if (key) perDayCount.set(key, (perDayCount.get(key) ?? 0) + 1)
  }

  // Fill a continuous window ending "today" so the chart reads as a timeline.
  const end = opts.now ?? new Date()
  const perDay: { date: string; deploys: number }[] = []
  for (let i = windowDays - 1; i >= 0; i--) {
    const day = new Date(end)
    day.setUTCDate(day.getUTCDate() - i)
    const key = day.toISOString().slice(0, 10)
    perDay.push({ date: key.slice(5), deploys: perDayCount.get(key) ?? 0 })
  }

  const finished = succeeded + failed
  const successRate = finished ? Math.round((succeeded / finished) * 100) : 0

  return {
    total: deployments.length,
    succeeded,
    failed,
    running,
    successRate,
    lastDeployAt,
    perDay,
    statusBreakdown: [
      { name: "Succeeded", value: succeeded },
      { name: "Failed", value: failed },
      { name: "In progress", value: running },
    ],
  }
}
