import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"

import { AppStatus } from "@/components/ui/app-status"
import { faBox, faDatabase } from "@/lib/icons"
import type { WorkspaceService } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"
import { serviceHref } from "@/lib/workspace"

export type ServiceRuntime = { status?: string; lastDeploy?: string; detail?: string }

/** The services of one environment: kind, status, address and last deploy. */
export function ServiceList({
  services,
  runtime,
}: {
  services: WorkspaceService[]
  /** Keyed by `external_id` (the stack name). */
  runtime: Record<string, ServiceRuntime>
}) {
  return (
    <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
      {services.map((service) => {
        const info = runtime[service.external_id] ?? {}
        const isDb = service.kind === "database"
        return (
          <li key={service.id}>
            <Link
              href={serviceHref(service)}
              className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <FontAwesomeIcon icon={isDb ? faDatabase : faBox} className="size-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{service.name}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {isDb ? info.detail || "Database" : service.domain || service.external_id}
                </span>
              </span>
              {info.lastDeploy ? (
                <span className="hidden text-xs text-muted-foreground md:block">
                  deployed {formatRelativeLabel(info.lastDeploy)}
                </span>
              ) : null}
              <AppStatus value={info.status || "unknown"} />
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
