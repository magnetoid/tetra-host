"use client"

import type { ReactNode } from "react"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { StatusBadge } from "@/components/ui/status-badge"
import { SOURCE_META, type DeploymentSource, type UnifiedDeployment } from "@/lib/deployments"
import { faChevronDown } from "@/lib/icons"
import { cn } from "@/lib/utils"

/** The source pill shown on every deployment card — the visual "where did this run" cue. */
export function SourceBadge({ source }: { source: DeploymentSource }) {
  const meta = SOURCE_META[source]
  return (
    <span
      title={meta.hint}
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 text-xs",
        source === "coolify"
          ? "border-border bg-muted text-muted-foreground"
          : "border-primary/30 bg-primary/10 text-primary",
      )}
    >
      {meta.label}
    </span>
  )
}

function subtitleFor(deployment: UnifiedDeployment): string {
  if (deployment.source === "app") return "one-click install"
  const ref = deployment.source === "coolify" ? deployment.branch : deployment.ref
  const short = deployment.commit ? `@${deployment.commit.slice(0, 7)}` : ""
  return `${ref || "—"}${short}`
}

/**
 * Universal deployment card — one accordion row rendered identically for every source
 * (git build, marketplace app, Coolify application). The header (source badge, status,
 * project, ref/commit, domain) is uniform; callers supply source-specific `actions` (the
 * buttons that light up per {@link capabilitiesFor}) and the expanded `children` body
 * (details + whichever log stream matches the source).
 */
export function DeploymentCard({
  deployment,
  expanded,
  onToggle,
  actions,
  children,
}: {
  deployment: UnifiedDeployment
  expanded: boolean
  onToggle: () => void
  actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border bg-muted transition-colors",
        expanded ? "border-primary/40" : "border-border hover:border-primary/30",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <FontAwesomeIcon
            icon={faChevronDown}
            className={cn(
              "h-3 w-3 shrink-0 text-muted-foreground transition-transform",
              expanded && "rotate-180",
            )}
          />
          <span className="truncate font-medium">{deployment.project}</span>
          <StatusBadge value={deployment.status} />
          <SourceBadge source={deployment.source} />
          <span className="truncate font-mono text-xs text-muted-foreground">
            {subtitleFor(deployment)}
          </span>
        </button>
        <div className="flex items-center gap-3">
          {deployment.domain ? (
            <a
              href={`https://${deployment.domain}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              {deployment.domain}
            </a>
          ) : null}
          {actions}
        </div>
      </div>

      {expanded ? (
        <div className="space-y-4 border-t border-border px-4 pb-4 pt-4">{children}</div>
      ) : null}
    </div>
  )
}
