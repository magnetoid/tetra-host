"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
import { faCircleCheck, faPlus, faTrash } from "@/lib/icons"
import type { DomainRecord, InstalledApp } from "@/lib/types"

const INPUT_CLASS =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

export function DomainsManager({
  domains,
  apps,
}: {
  domains: DomainRecord[]
  apps: InstalledApp[]
}) {
  const router = useRouter()
  const [hostname, setHostname] = useState("")
  const [project, setProject] = useState(apps[0]?.project ?? "")
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function call(path: string, init: RequestInit, key: string) {
    setPending(key)
    setError(null)
    try {
      const response = await fetch(path, init)
      const payload = (await response.json().catch(() => ({}))) as { detail?: string }
      if (!response.ok) {
        setError(payload.detail ?? "Request failed.")
        return false
      }
      router.refresh()
      return true
    } catch {
      setError("Unable to reach the control plane.")
      return false
    } finally {
      setPending(null)
    }
  }

  async function addDomain(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const ok = await call(
      "/api/proxy/domains",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, hostname }),
      },
      "add",
    )
    if (ok) setHostname("")
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <form
        onSubmit={addDomain}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4"
      >
        <label className="block text-sm">
          <span className="mb-2 block text-muted-foreground">App</span>
          <select
            aria-label="App"
            value={project}
            onChange={(event) => setProject(event.target.value)}
            className={INPUT_CLASS}
            required
          >
            {apps.length === 0 ? <option value="">no apps deployed</option> : null}
            {apps.map((app) => (
              <option key={app.project} value={app.project}>
                {app.name || app.project}
              </option>
            ))}
          </select>
        </label>
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-muted-foreground">Domain</span>
          <input
            aria-label="Domain"
            value={hostname}
            onChange={(event) => setHostname(event.target.value)}
            placeholder="www.example.com"
            className={`${INPUT_CLASS} w-full`}
            required
          />
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null || apps.length === 0}>
          {pending === "add" ? "…" : "Add domain"}
        </Button>
      </form>

      {domains.length === 0 ? (
        <EmptyState
          title="No custom domains yet"
          description="Attach your own domain to a deployed app — verification takes one TXT record."
        />
      ) : (
        <div className="space-y-3">
          {domains.map((domain) => (
            <div key={domain.id} className="rounded-2xl border border-border bg-muted p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-medium">{domain.hostname}</span>
                    <StatusBadge value={domain.status} />
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    → {domain.project}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {domain.status !== "verified" ? (
                    <Button
                      size="sm"
                      icon={faCircleCheck}
                      disabled={pending !== null}
                      onClick={() =>
                        call(`/api/proxy/domains/${domain.id}/verify`, { method: "POST" }, `verify:${domain.id}`)
                      }
                    >
                      {pending === `verify:${domain.id}` ? "…" : "Verify"}
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="danger"
                    icon={faTrash}
                    disabled={pending !== null}
                    onClick={() =>
                      call(`/api/proxy/domains/${domain.id}`, { method: "DELETE" }, `rm:${domain.id}`)
                    }
                  >
                    {pending === `rm:${domain.id}` ? "…" : "Remove"}
                  </Button>
                </div>
              </div>

              {domain.status !== "verified" ? (
                <div className="mt-3 rounded-xl border border-border bg-background/70 p-3 font-mono text-xs text-muted-foreground">
                  <div className="mb-1 text-muted-foreground">Publish these DNS records, then hit Verify:</div>
                  <div>
                    TXT&nbsp;&nbsp;&nbsp;{domain.txt_name} = &quot;{domain.txt_value}&quot;
                  </div>
                  <div>
                    CNAME&nbsp;{domain.hostname} → {domain.cname_target}
                  </div>
                </div>
              ) : (
                <div className="mt-2 text-xs text-muted-foreground">
                  Redeploy the app to route this domain at the edge.
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
