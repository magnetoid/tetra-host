import Link from "next/link"

import { fetchBackend } from "@/lib/api"
import type { StatusResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

// Always render fresh; the backend caches the underlying provider checks for 30s.
export const dynamic = "force-dynamic"

const OVERALL: Record<string, { label: string; dot: string; text: string }> = {
  operational: { label: "All systems operational", dot: "bg-status-ok", text: "text-status-ok" },
  degraded: { label: "Partial service degradation", dot: "bg-status-warn", text: "text-status-warn" },
  down: { label: "Major service outage", dot: "bg-status-err", text: "text-status-err" },
}

const DOT: Record<string, string> = {
  operational: "bg-status-ok",
  degraded: "bg-status-warn",
  down: "bg-status-err",
}

function fmt(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "" : d.toUTCString()
}

export default async function StatusPage() {
  const status = await fetchBackend<StatusResponse>("/status").catch(() => null)
  const overall = OVERALL[status?.overall ?? "down"] ?? OVERALL.down

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <div className="mb-8 flex items-center justify-between">
        <div className="text-sm font-medium text-muted-foreground">Tetra AI Cloud</div>
        <Link href="/status" className="text-xs text-muted-foreground transition-colors hover:text-foreground">
          Refresh
        </Link>
      </div>

      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="flex items-center gap-3">
          <span className={cn("size-3 rounded-full", overall.dot)} />
          <h1 className={cn("font-display text-xl font-semibold", overall.text)}>{overall.label}</h1>
        </div>

        {status ? (
          <div className="mt-6 divide-y divide-border">
            {status.components.map((c) => (
              <div key={c.name} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <div className="font-medium">{c.name}</div>
                  {c.detail ? (
                    <div className="truncate text-xs text-muted-foreground">{c.detail}</div>
                  ) : null}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={cn("size-2 rounded-full", DOT[c.status] ?? "bg-muted-foreground")} />
                  <span className="text-sm capitalize text-muted-foreground">{c.status}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-6 text-sm text-muted-foreground">
            The status feed is temporarily unavailable.
          </p>
        )}
      </div>

      {status?.updated_at ? (
        <div className="mt-4 text-center text-xs text-muted-foreground">
          Last checked {fmt(status.updated_at)}
        </div>
      ) : null}
    </main>
  )
}
