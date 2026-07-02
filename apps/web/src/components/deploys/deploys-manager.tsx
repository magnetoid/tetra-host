"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { DeployLogStream } from "@/components/deploys/deploy-log-stream"
import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
import { faArrowsRotate, faRocket, faTerminal } from "@/lib/icons"
import type { DeploymentRecord } from "@/lib/types"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

export function DeploysManager({ deployments }: { deployments: DeploymentRecord[] }) {
  const router = useRouter()
  const [gitUrl, setGitUrl] = useState("")
  const [name, setName] = useState("")
  const [ref, setRef] = useState("main")
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [streamId, setStreamId] = useState<string | null>(null)

  async function deploy(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending("deploy")
    setError(null)
    try {
      const response = await fetch("/api/proxy/deploys/git", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ git_url: gitUrl, name, ref }),
      })
      const payload = (await response.json().catch(() => ({}))) as {
        detail?: string
        deployment_id?: string
      }
      if (!response.ok) {
        setError(payload.detail ?? "Deploy failed to start.")
        return
      }
      setGitUrl("")
      setName("")
      if (payload.deployment_id) setStreamId(payload.deployment_id)
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function rollback(deploymentId: string) {
    setPending(`rollback:${deploymentId}`)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/deploys/${deploymentId}/rollback`, { method: "POST" })
      const payload = (await response.json().catch(() => ({}))) as {
        detail?: string
        deployment_id?: string
      }
      if (!response.ok) {
        setError(payload.detail ?? "Rollback failed to start.")
        return
      }
      if (payload.deployment_id) setStreamId(payload.deployment_id)
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={deploy}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4"
      >
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-zinc-400">Git repository</span>
          <input
            aria-label="Git repository"
            value={gitUrl}
            onChange={(event) => setGitUrl(event.target.value)}
            placeholder="https://github.com/you/app"
            className={`${INPUT_CLASS} w-full`}
            required
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-zinc-400">Name</span>
          <input
            aria-label="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="my-app"
            className={INPUT_CLASS}
            required
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-zinc-400">Branch</span>
          <input
            aria-label="Branch"
            value={ref}
            onChange={(event) => setRef(event.target.value)}
            className={`${INPUT_CLASS} w-28`}
          />
        </label>
        <Button type="submit" icon={faRocket} disabled={pending !== null}>
          {pending === "deploy" ? "…" : "Deploy"}
        </Button>
      </form>

      {streamId ? (
        <div className="rounded-2xl border border-border bg-muted p-4">
          <div className="mb-3 text-sm font-medium">Build log</div>
          <DeployLogStream key={streamId} deploymentId={streamId} />
        </div>
      ) : null}

      {deployments.length === 0 ? (
        <EmptyState
          title="No deployments yet"
          description="Deploy any git repository — Dockerfile if present, zero-config Nixpacks otherwise."
        />
      ) : (
        <div className="space-y-3">
          {deployments.map((deployment) => (
            <div
              key={deployment.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-muted p-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{deployment.project}</span>
                  <StatusBadge value={deployment.status} />
                  <span className="font-mono text-xs text-zinc-600">
                    {deployment.ref}
                    {deployment.commit ? `@${deployment.commit.slice(0, 7)}` : ""}
                  </span>
                </div>
                <div className="mt-1 text-sm text-zinc-500">
                  {deployment.domain ? (
                    <a
                      href={`https://${deployment.domain}`}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-zinc-300"
                    >
                      {deployment.domain}
                    </a>
                  ) : (
                    <span className="font-mono text-xs">{deployment.error || deployment.id.slice(0, 8)}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  icon={faTerminal}
                  disabled={pending !== null}
                  onClick={() => setStreamId(deployment.id)}
                >
                  Logs
                </Button>
                {deployment.status === "ready" && deployment.image ? (
                  <Button
                    size="sm"
                    icon={faArrowsRotate}
                    disabled={pending !== null}
                    onClick={() => rollback(deployment.id)}
                  >
                    {pending === `rollback:${deployment.id}` ? "…" : "Rollback to this"}
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
