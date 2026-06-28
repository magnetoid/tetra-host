import Link from "next/link"

import { SiteActions } from "@/components/sites/site-actions"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { SiteDeploymentRecord, SiteRecord } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

type SitesPageProps = {
  searchParams: Promise<{ refresh?: string; app?: string }>
}

export default async function SitesPage({ searchParams }: SitesPageProps) {
  const session = await requireConsoleSession()
  const params = await searchParams
  const refresh = params.refresh === "1" ? "1" : undefined
  const sites = await fetchBackend<SiteRecord[]>("/sites", {
    token: session.token,
    searchParams: { refresh },
  })

  let deployments: SiteDeploymentRecord[] = []
  if (params.app) {
    deployments = await fetchBackend<SiteDeploymentRecord[]>(
      `/sites/${params.app}/deployments`,
      { token: session.token },
    ).catch(() => [])
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Coolify backend"
        title="Sites"
        description="Operational inventory of Coolify applications with deployment-safe controls."
        action={<RefreshLink href="/sites?refresh=1" label="Refresh inventory" />}
      />

      <section className="grid gap-4">
        {sites.length > 0 ? (
          sites.map((site) => (
            <article
              key={site.id}
              className="rounded-2xl border border-border bg-zinc-950/70 p-5 transition hover:border-zinc-700"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-3">
                  <div className="grid h-10 w-10 place-items-center rounded-xl border border-border bg-background text-sm font-semibold">
                    {site.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h2 className="font-semibold">{site.name}</h2>
                    <a
                      className="text-sm text-zinc-500 hover:text-zinc-300"
                      href={`https://${site.primary_domain}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {site.primary_domain}
                    </a>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge value={site.environment || "Production"} />
                  <StatusBadge value={site.status} />
                </div>
              </div>

              <div className="mt-5 grid gap-3 text-sm md:grid-cols-4">
                <div>
                  <div className="text-zinc-500">Repository</div>
                  <div className="mt-1 truncate">{site.repository || "Not linked"}</div>
                </div>
                <div>
                  <div className="text-zinc-500">Environment</div>
                  <div className="mt-1">{site.environment || "Production"}</div>
                </div>
                <div>
                  <div className="text-zinc-500">Last update</div>
                  <div className="mt-1">{formatRelativeLabel(site.updated_at)}</div>
                </div>
                <div>
                  <div className="text-zinc-500">Health checks</div>
                  <div className="mt-1">
                    {site.healthcheck_enabled ? "Enabled" : "Unavailable"}
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <SiteActions applicationId={site.id} />
                <Link
                  href={`/sites?app=${site.id}`}
                  className="rounded-lg border border-border px-3 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900"
                >
                  View deployments
                </Link>
              </div>
            </article>
          ))
        ) : (
          <EmptyState
            title="No applications were returned from Coolify."
            description="Connect COOLIFY_URL and COOLIFY_TOKEN on the backend to load production data."
          />
        )}
      </section>

      {params.app ? (
        <section className="rounded-2xl border border-border bg-zinc-950/70 p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="font-semibold">Recent deployments</h2>
              <p className="mt-1 text-sm text-zinc-500">Application: {params.app}</p>
            </div>
            <Link href="/sites" className="text-sm text-zinc-400 hover:text-zinc-200">
              Clear
            </Link>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            {deployments.length > 0 ? (
              deployments.map((deployment) => (
                <div key={deployment.id} className="rounded-xl border border-border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{deployment.id}</div>
                    <StatusBadge value={deployment.status} />
                  </div>
                  <div className="mt-2 text-zinc-500">
                    Branch: {deployment.branch || "n/a"} · Commit: {deployment.commit || "n/a"} ·
                    Created: {formatRelativeLabel(deployment.created_at)}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-zinc-400">No deployments found for this application.</div>
            )}
          </div>
        </section>
      ) : null}
    </div>
  )
}
