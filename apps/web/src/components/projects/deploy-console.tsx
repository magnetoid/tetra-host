"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { DeploymentCard } from "@/components/deploys/deployment-card"
import { LogStream } from "@/components/projects/log-stream"
import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { unifyCoolify } from "@/lib/deployments"
import { faArrowsRotate, faRocket } from "@/lib/icons"
import type { ProjectActionResponse, ProjectDeploymentRecord } from "@/lib/types"

function isInProgress(status: string): boolean {
  return /(queue|build|progress|running|deploy|start|pending)/.test(status.toLowerCase())
}

export function DeployConsole({
  applicationId,
  projectName,
  initialDeployments,
}: {
  applicationId: string
  projectName?: string
  initialDeployments: ProjectDeploymentRecord[]
}) {
  const router = useRouter()
  const [expandedId, setExpandedId] = useState<string | null>(initialDeployments[0]?.id ?? null)
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
    const result = await postAction(
      `projects/${applicationId}/deploy${query}`,
      force ? "redeploy" : "deploy",
    )
    if (result?.deployment_id) setExpandedId(result.deployment_id)
    router.refresh()
  }

  async function cancelDeployment(deploymentId: string) {
    await postAction(
      `projects/${applicationId}/deployments/${deploymentId}/cancel`,
      `cancel:${deploymentId}`,
    )
    router.refresh()
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          icon={faRocket}
          disabled={pending !== null}
          onClick={() => triggerDeploy(false)}
        >
          {pending === "deploy" ? "Deploying…" : "Deploy"}
        </Button>
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

      {initialDeployments.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
          No deployments yet. Trigger one to see it stream here.
        </p>
      ) : (
        <div className="space-y-3">
          {initialDeployments.map((record) => {
            const deployment = unifyCoolify(record, projectName || applicationId)
            const expanded = expandedId === record.id
            return (
              <DeploymentCard
                key={record.id}
                deployment={deployment}
                expanded={expanded}
                onToggle={() => setExpandedId(expanded ? null : record.id)}
                actions={
                  isInProgress(record.status) ? (
                    <Button
                      size="sm"
                      icon={faArrowsRotate}
                      disabled={pending !== null}
                      onClick={() => void cancelDeployment(record.id)}
                    >
                      {pending === `cancel:${record.id}` ? "Cancelling…" : "Cancel"}
                    </Button>
                  ) : null
                }
              >
                <LogStream key={record.id} applicationId={applicationId} deploymentId={record.id} />
              </DeploymentCard>
            )
          })}
        </div>
      )}
    </div>
  )
}
