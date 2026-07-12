import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B"
  }

  const units = ["B", "KB", "MB", "GB", "TB"]
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

export function formatCompactNumber(value: number): string {
  if (!Number.isFinite(value) || value === 0) {
    return "0"
  }
  const abs = Math.abs(value)
  if (abs < 1000) {
    return `${Math.round(value)}`
  }
  const units = [
    { limit: 1e9, suffix: "B" },
    { limit: 1e6, suffix: "M" },
    { limit: 1e3, suffix: "k" },
  ]
  for (const { limit, suffix } of units) {
    if (abs >= limit) {
      const scaled = value / limit
      return `${scaled.toFixed(scaled >= 10 ? 0 : 1)}${suffix}`
    }
  }
  return `${value}`
}

export function formatRelativeLabel(value: string): string {
  if (!value) {
    return "Recently updated"
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  const deltaMs = Date.now() - date.getTime()
  const deltaMinutes = Math.max(1, Math.round(deltaMs / 60000))
  if (deltaMinutes < 60) {
    return `${deltaMinutes}m ago`
  }

  const deltaHours = Math.round(deltaMinutes / 60)
  if (deltaHours < 24) {
    return `${deltaHours}h ago`
  }

  const deltaDays = Math.round(deltaHours / 24)
  return `${deltaDays}d ago`
}

export function statusTone(value: string): "positive" | "warning" | "critical" | "neutral" {
  const normalized = value.toLowerCase()
  if (normalized.includes("connected") || normalized.includes("running")) {
    return "positive"
  }
  if (normalized.includes("degraded") || normalized.includes("unknown")) {
    return "warning"
  }
  if (normalized.includes("unhealthy") || normalized.includes("exited") || normalized.includes("missing")) {
    return "critical"
  }
  return "neutral"
}

export type AppStatusView = {
  label: string
  tone: "positive" | "warning" | "critical" | "neutral" | "info"
  /** Transitional state — the dot should pulse. */
  pulse: boolean
}

/**
 * Turn a raw provider status (Coolify's `running:healthy`, `exited:unhealthy`,
 * `restarting`, `0:unhealthy`, `unknown`, …) into a clear human state, so it's
 * obvious whether an app is running, stopped, or mid-deploy.
 */
export function normalizeStatus(value: string): AppStatusView {
  const s = (value || "").toLowerCase()
  if (/(deploy|build|queued|in.?progress|pending|starting|restarting|created)/.test(s)) {
    return { label: "Deploying", tone: "info", pulse: true }
  }
  if (s.includes("running") && s.includes("unhealthy")) {
    return { label: "Unhealthy", tone: "warning", pulse: false }
  }
  if (s.includes("running") || (s.includes("healthy") && !s.includes("unhealthy")) || s.includes("connected")) {
    return { label: "Running", tone: "positive", pulse: false }
  }
  if (/(exited|stopped|inactive|offline)/.test(s) || /^0[:_-]/.test(s)) {
    return { label: "Stopped", tone: "neutral", pulse: false }
  }
  if (/(fail|error|crash)/.test(s)) {
    return { label: "Failed", tone: "critical", pulse: false }
  }
  if (s.includes("degraded")) {
    return { label: "Degraded", tone: "warning", pulse: false }
  }
  if (!s || s === "unknown") {
    return { label: "Unknown", tone: "neutral", pulse: false }
  }
  return { label: value.charAt(0).toUpperCase() + value.slice(1), tone: statusTone(value), pulse: false }
}

export function safeNextPath(value: string | undefined): string {
  if (!value || !value.startsWith("/")) {
    return "/dashboard"
  }
  return value
}
