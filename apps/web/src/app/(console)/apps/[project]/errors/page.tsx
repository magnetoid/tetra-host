import Link from "next/link"

import { ErrorIssuesTable } from "@/components/apps/error-issues-table"
import { Card, CardHeader } from "@/components/ui/card"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { ProjectErrors } from "@/lib/types"

export default async function ErrorsPage({ params }: { params: Promise<{ project: string }> }) {
  const session = await requireConsoleSession()
  const { project } = await params

  const errorsRes = await fetchDegraded<ProjectErrors | null>(
    `/apps/${encodeURIComponent(project)}/errors`,
    "App errors",
    null,
    { token: session.token },
  )
  const errors = errorsRes.data

  const header = (
    <>
      <Link href="/apps" className="text-sm text-muted-foreground hover:text-foreground">
        ← Apps
      </Link>
      <PageHeader
        eyebrow="Errors"
        title={project}
        description="Unresolved exceptions captured for this app, via GlitchTip."
      />
      <DegradedBanner sources={degradedSources([errorsRes])} />
    </>
  )

  // A degraded fetch (errors === null) must not read as "not connected" — the
  // banner above already explains the outage.
  if (!errors) {
    return <div className="space-y-6">{header}</div>
  }

  if (!errors.configured) {
    return (
      <div className="space-y-6">
        {header}
        <EmptyState
          title="Error tracking isn't connected yet"
          description="A platform admin can connect a self-hosted GlitchTip instance (set GLITCHTIP_URL) to surface exceptions, stack traces, and event counts here."
        />
      </div>
    )
  }

  if (!errors.ready) {
    return (
      <div className="space-y-6">
        {header}
        <EmptyState
          title="Error tracking not available for this app"
          description={errors.reason || "This app can't be attached to error tracking yet."}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {header}

      {errors.dsn ? (
        <Card>
          <CardHeader title="SDK DSN" action="Point your app's Sentry-compatible SDK here" />
          <pre className="mt-4 overflow-x-auto rounded-xl border border-border bg-code p-4 font-mono text-xs text-code-foreground">
            {errors.dsn}
          </pre>
        </Card>
      ) : null}

      <ErrorIssuesTable app={project} issues={errors.issues} />
    </div>
  )
}
