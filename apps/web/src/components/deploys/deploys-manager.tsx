"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { DeployLogStream } from "@/components/deploys/deploy-log-stream"
import { DeploymentCard } from "@/components/deploys/deployment-card"
import { ExplainButton } from "@/components/deploys/explain-button"
import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { capabilitiesFor, unifyNative } from "@/lib/deployments"
import { faArrowsRotate, faRocket } from "@/lib/icons"
import type { DeploymentRecord } from "@/lib/types"
import { cn, formatRelativeLabel } from "@/lib/utils"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

export function DeploysManager({ deployments }: { deployments: DeploymentRecord[] }) {
  const router = useRouter()
  const [gitUrl, setGitUrl] = useState("")
  const [name, setName] = useState("")
  const [ref, setRef] = useState("main")
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Which deployment card is expanded (accordion). Its info + live logs render inline.
  const [expandedId, setExpandedId] = useState<string | null>(null)

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
      // Open the new deployment's card so its build log streams inline once it lands.
      if (payload.deployment_id) setExpandedId(payload.deployment_id)
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
      if (payload.deployment_id) setExpandedId(payload.deployment_id)
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
          <span className="mb-2 block text-muted-foreground">Git repository</span>
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
          <span className="mb-2 block text-muted-foreground">Name</span>
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
          <span className="mb-2 block text-muted-foreground">Branch</span>
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

      {deployments.length === 0 ? (
        <EmptyState
          title="No deployments yet"
          description="Deploy any git repository — Dockerfile if present, zero-config Nixpacks otherwise."
        />
      ) : (
        <div className="space-y-3">
          {deployments.map((record) => {
            const deployment = unifyNative(record)
            const caps = capabilitiesFor(deployment)
            const expanded = expandedId === record.id
            return (
              <DeploymentCard
                key={record.id}
                deployment={deployment}
                expanded={expanded}
                onToggle={() => setExpandedId(expanded ? null : record.id)}
                actions={
                  caps.rollback ? (
                    <Button
                      size="sm"
                      icon={faArrowsRotate}
                      disabled={pending !== null}
                      onClick={() => rollback(record.id)}
                    >
                      {pending === `rollback:${record.id}` ? "…" : "Rollback to this"}
                    </Button>
                  ) : null
                }
              >
                <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-4">
                  <Detail label="Commit" value={record.commit || "—"} mono />
                  <Detail label="Branch" value={record.ref || "—"} mono />
                  <Detail label="Builder" value={record.builder || "—"} />
                  <Detail label="Port" value={record.port ? String(record.port) : "—"} mono />
                  <Detail label="Image" value={record.image || "not built"} mono />
                  <Detail label="Created" value={formatRelativeLabel(record.created_at)} />
                  <Detail label="Deployment" value={record.id} mono />
                  {record.git_url ? <Detail label="Repository" value={record.git_url} mono /> : null}
                </dl>

                {record.error ? (
                  <div className="space-y-2">
                    <AlertBanner tone="error">{record.error}</AlertBanner>
                    <ExplainButton deploymentId={record.id} />
                  </div>
                ) : null}

                <div>
                  <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Build log
                  </div>
                  <DeployLogStream deploymentId={record.id} />
                </div>
              </DeploymentCard>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Detail({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("mt-0.5 truncate", mono && "font-mono text-xs")}>{value}</dd>
    </div>
  )
}
