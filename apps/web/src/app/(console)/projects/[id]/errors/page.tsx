import { Card, CardHeader } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectErrors } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

export default async function ErrorsPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await requireConsoleSession()
  const { id } = await params

  const errors = await fetchBackend<ProjectErrors>(`/projects/${id}/errors`, {
    token: session.token,
  }).catch(() => null)

  const header = (
    <PageHeader
      eyebrow="Observability"
      title="Errors"
      description="Unresolved exceptions captured for this project, via GlitchTip."
    />
  )

  if (!errors || !errors.configured) {
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
          title="Error tracking not available for this project"
          description={errors.reason || "This project can't be attached to error tracking yet."}
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
          <pre className="mt-4 overflow-x-auto rounded-xl border border-border bg-black/60 p-4 font-mono text-xs text-zinc-300">
            {errors.dsn}
          </pre>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Unresolved issues" action={`${errors.issues.length} open`} />
        <div className="mt-4">
          {errors.issues.length === 0 ? (
            <p className="text-sm text-muted-foreground">No unresolved errors. 🎉</p>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-border">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-background/60 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Level</th>
                    <th className="px-4 py-3 font-medium">Issue</th>
                    <th className="px-4 py-3 text-right font-medium">Events</th>
                    <th className="px-4 py-3 text-right font-medium">Users</th>
                    <th className="px-4 py-3 text-right font-medium">Last seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-background">
                  {errors.issues.map((issue) => (
                    <tr key={issue.id}>
                      <td className="px-4 py-3">
                        <StatusBadge value={issue.level} />
                      </td>
                      <td className="px-4 py-3">
                        {issue.permalink ? (
                          <a
                            href={issue.permalink}
                            target="_blank"
                            rel="noreferrer"
                            className="font-medium text-foreground hover:text-foreground"
                          >
                            {issue.title}
                          </a>
                        ) : (
                          <span className="font-medium text-foreground">{issue.title}</span>
                        )}
                        {issue.culprit ? (
                          <div className="mt-0.5 font-mono text-xs text-muted-foreground">{issue.culprit}</div>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">{issue.count}</td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-muted-foreground">
                        {issue.user_count}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                        {issue.last_seen ? formatRelativeLabel(issue.last_seen) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
