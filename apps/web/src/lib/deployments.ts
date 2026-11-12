/**
 * Universal deployment model — one shape for every deployment regardless of where it
 * runs. Tetra deploys a project on the Tetra Engine in one of two ways: a git build
 * ("git") or a marketplace app install ("app"). The console renders both with the same
 * card; only the available *actions* differ (git builds carry richer controls). This module
 * is the single source of truth for that mapping so no surface re-derives it.
 */

import type { DeploymentRecord } from "@/lib/types"

export type DeploymentSource = "git" | "app"

export interface UnifiedDeployment {
  id: string
  /** Grouping key — the project this deployment belongs to. */
  project: string
  source: DeploymentSource
  status: string
  createdAt: string
  ref?: string
  commit?: string
  domain?: string
  image?: string
  builder?: string
  port?: number
  gitUrl?: string
  error?: string
}

/** What a deployment can do, by source. Platform (git) deployments are the richest. */
export interface DeploymentCapabilities {
  /** Roll back to this build (git only, once it has a built image). */
  rollback: boolean
  /** AI-explain a failed build (git only, when there's an error). */
  explain: boolean
  /** Stream build logs (all sources). */
  logs: boolean
  /** Cancel a git build that is still queued or building. */
  cancel: boolean
}

const IN_PROGRESS = new Set(["queued", "building"])

export function capabilitiesFor(deployment: UnifiedDeployment): DeploymentCapabilities {
  if (deployment.source === "app") {
    return { rollback: false, explain: false, logs: true, cancel: false }
  }
  // git — the native Tetra-engine build path, richest controls.
  return {
    rollback: deployment.status === "ready" && Boolean(deployment.image),
    explain: Boolean(deployment.error),
    logs: true,
    cancel: IN_PROGRESS.has(deployment.status),
  }
}

/** Display metadata for the source badge shown on every card. */
export const SOURCE_META: Record<DeploymentSource, { label: string; hint: string }> = {
  git: { label: "Platform", hint: "Tetra engine · git build" },
  app: { label: "Marketplace app", hint: "Tetra engine · one-click install" },
}

function nativeSource(record: DeploymentRecord): DeploymentSource {
  if (record.source === "git" || record.source === "app") return record.source
  return record.builder === "app" ? "app" : "git"
}

/** Map a native Tetra-engine deployment (git build or app install) into the universal shape. */
export function unifyNative(record: DeploymentRecord): UnifiedDeployment {
  return {
    id: record.id,
    project: record.project,
    source: nativeSource(record),
    status: record.status,
    createdAt: record.created_at,
    ref: record.ref,
    commit: record.commit,
    domain: record.domain,
    image: record.image,
    builder: record.builder,
    port: record.port,
    gitUrl: record.git_url,
    error: record.error,
  }
}
