import Link from "next/link"

import { cn, formatRelativeLabel } from "@/lib/utils"
import type { RecentDeployment } from "@/lib/types"

const STATUS: Record<string, { label: string; dot: string; text: string }> = {
  ready: { label: "Ready", dot: "bg-status-ok", text: "text-status-ok" },
  building: { label: "Building", dot: "bg-status-live", text: "text-status-live" },
  error: { label: "Failed", dot: "bg-status-err", text: "text-status-err" },
  queued: { label: "Queued", dot: "bg-muted-foreground", text: "text-muted-foreground" },
}

function statusOf(value: string) {
  return STATUS[value] ?? { label: value || "—", dot: "bg-muted-foreground", text: "text-muted-foreground" }
}

/**
 * Editorial deployments table — status dot · project · commit/ref · status ·
 * relative time. Real data from /dashboard's recent_deployments.
 */
export function DeploymentsPanel({ deployments }: { deployments: RecentDeployment[] }) {
  return (
    <section>
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Deployments</h2>
        <Link href="/projects" className="text-sm text-primary transition-colors hover:text-primary/80">
          View all →
        </Link>
      </div>

      {deployments.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
          No deployments yet. Ship from a Git repo to see them here.
        </div>
      ) : (
        <div className="divide-y divide-border border-t border-border">
          {deployments.map((d) => {
            const s = statusOf(d.status)
            return (
              <div key={d.id} className="flex items-center gap-4 py-3 text-sm">
                <span className={cn("size-1.5 shrink-0 rounded-full", s.dot)} />
                <div className="w-40 shrink-0 truncate font-medium">{d.project}</div>
                <div className="flex min-w-0 flex-1 items-center gap-2 font-mono text-xs text-muted-foreground">
                  {d.commit ? <span className="text-foreground">{d.commit}</span> : null}
                  <span className="truncate">{d.ref}</span>
                </div>
                <div className={cn("w-16 shrink-0 text-right font-medium", s.text)}>{s.label}</div>
                <div className="w-16 shrink-0 text-right font-mono text-xs text-muted-foreground">
                  {d.created_at ? formatRelativeLabel(d.created_at) : "—"}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
