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

export function safeNextPath(value: string | undefined): string {
  if (!value || !value.startsWith("/")) {
    return "/dashboard"
  }
  return value
}
