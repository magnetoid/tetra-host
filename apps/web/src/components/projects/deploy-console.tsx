"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { DeploymentCard } from "@/components/deploys/deployment-card"
import { LogStream } from "@/components/projects/log-stream"
import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
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
  const { run, pending, error } = useAction()
  const [expandedId, setExpandedId] = useState<string | null>(initialDeployments[0]?.id ?? null)
  const [message, setMessage] = useState<string | null>(null)

  function postAction(path: string, label: string, onPayload?: (payload: ProjectActionResponse) => void) {
    setMessage(null)
    return run(
      async () => {
        const payload = await apiFetch<ProjectActionResponse>(`/api/proxy/${path}`, {
          method: "POST",
          errorMessage: "Action failed.",
        })
        setMessage(payload.message ?? "Action queued.")
        onPayload?.(payload)
      },
      { key: label },
    )
  }

  function triggerDeploy(force: boolean) {
    const query = force ? "?force=1" : ""
    return postAction(
      `projects/${applicationId}/deploy${query}`,
      force ? "redeploy" : "deploy",
      (payload) => {
        if (payload.deployment_id) setExpandedId(payload.deployment_id)
      },
    )
  }

  function cancelDeployment(deploymentId: string) {
    return postAction(
      `projects/${applicationId}/deployments/${deploymentId}/cancel`,
      `cancel:${deploymentId}`,
    )
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
