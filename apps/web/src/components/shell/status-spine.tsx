"use client"

import { useEffect, useState } from "react"

import type { DashboardResponse, ProviderStatus, ProviderSummary } from "@/lib/types"
import { cn } from "@/lib/utils"

// The signature element: a terminal-style provider-health strip under the topbar.
// Fetched client-side so it never blocks a page's SSR (provider status can be slow
// to compute upstream); it simply resolves from skeleton dots once ready.
const DOT: Record<ProviderStatus, string> = {
  connected: "bg-status-ok",
  degraded: "bg-status-warn",
  not_configured: "bg-muted-foreground/40",
}

const LABEL: Record<ProviderStatus, string> = {
  connected: "operational",
  degraded: "degraded",
  not_configured: "not configured",
}

export function StatusSpine() {
  const [providers, setProviders] = useState<ProviderSummary[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    fetch("/api/proxy/dashboard", { headers: { Accept: "application/json" } })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data: DashboardResponse) => {
        if (active) setProviders(data.providers)
      })
      .catch(() => {
        if (active) setFailed(true)
      })
    return () => {
      active = false
    }
  }, [])

  // A broken health probe shouldn't render a broken strip — just omit it.
  if (failed) return null

  const healthy = providers?.filter((p) => p.status === "connected").length ?? 0
  const total = providers?.length ?? 0

  return (
    <div className="flex items-center gap-x-5 overflow-x-auto border-b border-border bg-muted/30 px-6 py-1.5 text-xs">
      {providers === null ? (
        Array.from({ length: 4 }).map((_, i) => (
          <span key={i} className="flex shrink-0 items-center gap-1.5">
            <span className="size-1.5 animate-pulse rounded-full bg-foreground/20" />
            <span className="h-2 w-16 animate-pulse rounded bg-foreground/10" />
          </span>
        ))
      ) : (
        <>
          {providers.map((provider) => (
            <span
              key={provider.name}
              className="flex shrink-0 items-center gap-1.5"
              title={`${provider.name}: ${provider.detail}`}
            >
              <span className={cn("size-1.5 rounded-full", DOT[provider.status])} />
              <span className="font-mono text-foreground">{provider.name}</span>
              <span className="hidden text-muted-foreground sm:inline">
                {LABEL[provider.status]}
              </span>
            </span>
          ))}
          <span className="ml-auto shrink-0 font-mono tabular-nums text-muted-foreground">
            {healthy}/{total} operational
          </span>
        </>
      )}
    </div>
  )
}
