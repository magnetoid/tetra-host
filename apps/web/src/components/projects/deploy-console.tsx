"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { LogStream } from "@/components/projects/log-stream"
import { AlertBanner } from "@/components/ui/alert-banner"
import { StatusBadge } from "@/components/ui/status-badge"
import type { ProjectActionResponse, ProjectDeploymentRecord } from "@/lib/types"
import { cn, formatRelativeLabel } from "@/lib/utils"

function isInProgress(status: string): boolean {
  return /(queue|build|progress|running|deploy|start|pending)/.test(status.toLowerCase())
}

export function DeployConsole({
  applicationId,
  initialDeployments,
}: {
  applicationId: string
  initialDeployments: ProjectDeploymentRecord[]
}) {
  const router = useRouter()
  const [selectedId, setSelectedId] = useState<string | null>(
    initialDeployments[0]?.id ?? null,
  )
  const [pending, setPending] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function postAction(path: string, label: string): Promise<ProjectActionResponse | null> {
    setPending(label)
    setMessage(null)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/${path}`, { method: "POST" })
      const payload = (await response.json()) as ProjectActionResponse & { detail?: string }
      if (!response.ok) {
        setError(payload.detail ?? "Action failed.")
        return null
      }
      setMessage(payload.message ?? "Action queued.")
      return payload
    } catch {
      setError("Unable to reach the control plane.")
      return null
    } finally {
      setPending(null)
    }
  }

  async function triggerDeploy(force: boolean) {
    const query = force ? "?force=1" : ""
    const result = await postAction(`projects/${applicationId}/deploy${query}`, force ? "redeploy" : "deploy")
    if (result?.deployment_id) {
      setSelectedId(result.deployment_id)
    }
    router.refresh()
  }

  async function cancelDeployment(deploymentId: string) {
    await postAction(`projects/${applicationId}/deployments/${deploymentId}/cancel`, `cancel:${deploymentId}`)
    router.refresh()
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={pending !== null}
          onClick={() => triggerDeploy(false)}
          className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-foreground/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending === "deploy" ? "Deploying…" : "Deploy"}
        </button>
        <button
          type="button"
          disabled={pending !== null}
          onClick={() => triggerDeploy(true)}
          className="rounded-lg border border-border px-4 py-2 text-sm text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending === "redeploy" ? "Rebuilding…" : "Force rebuild"}
        </button>
        <button
          type="button"
          disabled={pending !== null}
          onClick={() => router.refresh()}
          className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent disabled:opacity-60"
        >
          Refresh
        </button>
      </div>

      {message ? <AlertBanner tone="success">{message}</AlertBanner> : null}
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">Deployments</h3>
          {initialDeployments.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
              No deployments yet. Trigger one to see it stream here.
            </p>
          ) : (
            initialDeployments.map((deployment) => {
              const selected = deployment.id === selectedId
              return (
                <div
                  key={deployment.id}
                  className={cn(
                    "rounded-xl border p-3 transition-colors",
                    selected
                      ? "border-primary bg-accent"
                      : "border-border hover:border-primary/30 hover:bg-accent",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedId(deployment.id)}
                    className="w-full text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-muted-foreground">
                        {deployment.commit ? deployment.commit.slice(0, 7) : deployment.id.slice(0, 7)}
                      </span>
                      <StatusBadge value={deployment.status} />
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 font-mono text-xs text-muted-foreground">
                      <span>{deployment.branch || "—"}</span>
                      <span>{formatRelativeLabel(deployment.created_at)}</span>
                    </div>
                  </button>
                  {isInProgress(deployment.status) ? (
                    <button
                      type="button"
                      disabled={pending !== null}
                      onClick={() => void cancelDeployment(deployment.id)}
                      className="mt-2 inline-flex rounded-md border border-status-err/25 px-2 py-1 text-xs text-status-err transition-colors hover:bg-status-err/10 disabled:opacity-60"
                    >
                      {pending === `cancel:${deployment.id}` ? "Cancelling…" : "Cancel"}
                    </button>
                  ) : null}
                </div>
              )
            })
          )}
        </div>

        <div>
          {selectedId ? (
            <LogStream key={selectedId} applicationId={applicationId} deploymentId={selectedId} />
          ) : (
            <div className="grid h-full min-h-[12rem] place-items-center rounded-2xl border border-dashed border-border text-sm text-muted-foreground">
              Select a deployment to view its build logs.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
