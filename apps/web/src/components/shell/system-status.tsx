"use client"

import { useEffect, useState } from "react"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { DashboardResponse, ProviderSummary } from "@/lib/types"
import { cn } from "@/lib/utils"

/**
 * One compact provider-health indicator in the top bar (replaces the old status
 * strip). Fetched client-side so slow provider probes never block a page render;
 * the tooltip lists each provider.
 */
export function SystemStatus() {
  const [providers, setProviders] = useState<ProviderSummary[] | null>(null)

  useEffect(() => {
    let active = true
    fetch("/api/proxy/dashboard", { headers: { Accept: "application/json" } })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data: DashboardResponse) => {
        if (active) setProviders(data.providers)
      })
      .catch(() => {
        if (active) setProviders([])
      })
    return () => {
      active = false
    }
  }, [])

  if (providers === null || providers.length === 0) return null

  const degraded = providers.filter((p) => p.status === "degraded")
  const connected = providers.filter((p) => p.status === "connected")
  // "Normal" only when something is actually connected — an unconfigured
  // install must not read as healthy.
  const tone = degraded.length ? "warn" : connected.length ? "ok" : "idle"
  const label = degraded.length
    ? `${degraded.length} ${degraded.length === 1 ? "issue" : "issues"}`
    : connected.length
      ? "All systems normal"
      : "Providers not set up"

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            "hidden h-7 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium md:inline-flex",
            tone === "warn" ? "bg-status-warn-soft text-status-warn" : "text-muted-foreground hover:bg-accent",
          )}
        >
          <span
            className={cn(
              "size-1.5 rounded-full",
              tone === "warn" ? "bg-status-warn" : tone === "ok" ? "bg-status-ok" : "bg-muted-foreground",
            )}
          />
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent align="end" className="w-64">
        <ul className="space-y-1">
          {providers.map((p) => (
            <li key={p.name} className="flex items-center justify-between gap-3">
              <span>{p.name}</span>
              <span
                className={cn(
                  p.status === "connected" && "text-status-ok",
                  p.status === "degraded" && "text-status-warn",
                  p.status === "not_configured" && "opacity-70",
                )}
              >
                {p.status === "connected" ? "OK" : p.status === "degraded" ? "Degraded" : "Not set up"}
              </span>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  )
}
