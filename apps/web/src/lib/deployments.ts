/**
 * Universal deployment model — one shape for every deployment regardless of where it
 * runs. Tetra deploys a project in one of three ways: a git build ("git") or a
 * marketplace app install ("app") on the native Tetra engine, or a Coolify-backed
 * application ("coolify"). The console renders them all with the same card; only the
 * available *actions* differ (platform deployments carry richer controls). This module
 * is the single source of truth for that mapping so no surface re-derives it.
 */

import type { DeploymentRecord, ProjectDeploymentRecord } from "@/lib/types"

export type DeploymentSource = "git" | "app" | "coolify"

export interface UnifiedDeployment {
  id: string
  /** Grouping key — the project this deployment belongs to. */
  project: string
  source: DeploymentSource
  status: string
  createdAt: string
  ref?: string
  commit?: string
  branch?: string
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
  /** Trigger a fresh redeploy (Coolify applications). */
  redeploy: boolean
  /** Stream build logs (all sources). */
  logs: boolean
}

export function capabilitiesFor(deployment: UnifiedDeployment): DeploymentCapabilities {
  if (deployment.source === "coolify") {
    return { rollback: false, explain: false, redeploy: true, logs: true }
  }
  if (deployment.source === "app") {
    return { rollback: false, explain: false, redeploy: false, logs: true }
  }
  // git — the native Tetra-engine build path, richest controls.
  return {
    rollback: deployment.status === "ready" && Boolean(deployment.image),
    explain: Boolean(deployment.error),
    redeploy: false,
    logs: true,
  }
}

/** Display metadata for the source badge shown on every card. */
export const SOURCE_META: Record<DeploymentSource, { label: string; hint: string }> = {
  git: { label: "Platform", hint: "Tetra engine · git build" },
  app: { label: "Marketplace app", hint: "Tetra engine · one-click install" },
  coolify: { label: "Coolify", hint: "Coolify-backed application" },
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

/** Map a Coolify application deployment into the universal shape (needs the project name). */
export function unifyCoolify(
  record: ProjectDeploymentRecord,
  project: string,
): UnifiedDeployment {
  return {
    id: record.id,
    project,
    source: "coolify",
    status: record.status,
    createdAt: record.created_at,
    branch: record.branch,
    commit: record.commit,
  }
}
