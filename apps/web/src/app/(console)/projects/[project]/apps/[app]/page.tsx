import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { notFound } from "next/navigation"

import { DegradedBanner } from "@/components/ui/degraded-banner"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import {
  faBug,
  faChartLine,
  faEarthAmericas,
  faGear,
  faKey,
  faListCheck,
  faTerminal,
} from "@/lib/icons"
import type { ProjectRecord } from "@/lib/types"

type AppOverviewProps = {
  params: Promise<{ project: string; app: string }>
}

// The tabs a user drills into from the overview — base info here, everything
// else one click away (Deployments, Logs, Env, Domains, Metrics, Errors, Settings).
const SECTIONS = [
  { slug: "deployments", label: "Deployments", icon: faListCheck, desc: "Build history, redeploy, rollback, and live logs." },
  { slug: "logs", label: "Logs", icon: faTerminal, desc: "Runtime logs from the running container." },
  { slug: "env", label: "Environment", icon: faKey, desc: "Variables and secrets injected at deploy." },
  { slug: "domains", label: "Domains", icon: faEarthAmericas, desc: "Custom domains and TLS for this app." },
  { slug: "metrics", label: "Metrics", icon: faChartLine, desc: "Deploy stats and traffic analytics." },
  { slug: "errors", label: "Errors", icon: faBug, desc: "Unresolved issues from error tracking." },
  { slug: "settings", label: "Settings", icon: faGear, desc: "Build, run, ports, and app configuration." },
] as const

function Fact({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className={`mt-1 truncate text-sm text-foreground ${mono ? "font-mono" : ""}`}>
        {value || "—"}
      </dd>
    </div>
  )
}

/**
 * An app's home is now a real overview: base info about the app plus one-click
 * entry to every section (Deployments, Logs, Env, Domains, Metrics, Errors,
 * Settings) — instead of bouncing straight to Deployments.
 */
export default async function AppOverviewPage({ params }: AppOverviewProps) {
  const session = await requireConsoleSession()
  const { project, app } = await params

  const projectsRes = await fetchDegraded<ProjectRecord[]>("/projects", "Projects", [], {
    token: session.token,
  })
  const record = projectsRes.data.find((p) => p.id === app)

  if (!record && !projectsRes.degraded) {
    notFound()
  }

  const base = `/projects/${project}/apps/${app}`
  const updated = record?.updated_at ? new Date(record.updated_at).toLocaleString() : ""

  return (
    <div className="space-y-6">
      <DegradedBanner sources={degradedSources([projectsRes])} />

      {record ? (
        <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-foreground">App details</h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Fact label="Status" value={record.status} mono={false} />
            <Fact label="Primary domain" value={record.primary_domain} />
            <Fact label="Environment" value={record.environment} />
            <Fact label="Source" value={record.repository} />
            <Fact label="Build pack" value={record.build_pack || ""} />
            <Fact label="Last updated" value={updated} mono={false} />
          </dl>
        </section>
      ) : null}

      <section>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Manage</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {SECTIONS.map((s) => (
            <Link
              key={s.slug}
              href={`${base}/${s.slug}`}
              className="group flex items-start gap-3 rounded-lg border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40 hover:bg-accent"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-background text-primary">
                <FontAwesomeIcon icon={s.icon} className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <div className="font-medium">{s.label}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">{s.desc}</div>
              </div>
              <span className="ml-auto text-muted-foreground transition-transform group-hover:translate-x-0.5">
                →
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
