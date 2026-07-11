import { AreaChart } from "@/components/tremor/area-chart"
import { BarChart } from "@/components/tremor/bar-chart"
import { BarList } from "@/components/tremor/bar-list"
import { DonutChart } from "@/components/tremor/donut-chart"
import { Card, CardHeader } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { computeDeployStats } from "@/lib/deploy-stats"
import {
  faChartBar,
  faCircleCheck,
  faGaugeHigh,
  faHourglassHalf,
  faRocket,
  faTriangleExclamation,
  faUsers,
} from "@/lib/icons"
import type { ProjectAnalytics, ProjectDeploymentRecord } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

function fmtDuration(seconds: number): string {
  if (!seconds) return "0s"
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m ? `${m}m ${s}s` : `${s}s`
}

export default async function MetricsPage({ params }: { params: Promise<{ app: string }> }) {
  const session = await requireConsoleSession()
  const { app } = await params

  const [analytics, deployments] = await Promise.all([
    fetchBackend<ProjectAnalytics>(`/projects/${app}/analytics?period=7d`, {
      token: session.token,
    }).catch(() => null),
    fetchBackend<ProjectDeploymentRecord[]>(`/projects/${app}/deployments`, {
      token: session.token,
    }).catch(() => [] as ProjectDeploymentRecord[]),
  ])

  const stats = computeDeployStats(deployments)

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Observability"
        title="Metrics"
        description="Deployment health and reliability for this project, plus privacy-first web analytics."
      />

      {/* ── Deployment statistics — always available, derived from deploy history ── */}
      <section className="space-y-4">
        <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Deployments
        </h2>

        {stats.total === 0 ? (
          <EmptyState
            title="No deployments yet"
            description="Trigger a deployment to start tracking success rate, failures, and activity here."
          />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                icon={faRocket}
                label="Total deployments"
                value={stats.total}
                hint={`${stats.running} in progress`}
                accent="text-primary"
              />
              <StatCard
                icon={faCircleCheck}
                label="Success rate"
                value={`${stats.successRate}%`}
                hint={`${stats.succeeded} succeeded of ${stats.succeeded + stats.failed} finished`}
                accent="text-status-ok"
              />
              <StatCard
                icon={faTriangleExclamation}
                label="Failed"
                value={stats.failed}
                hint={stats.total ? `${Math.round((stats.failed / stats.total) * 100)}% of all runs` : ""}
                accent="text-status-err"
              />
              <StatCard
                icon={faHourglassHalf}
                label="Last deploy"
                value={stats.lastDeployAt ? formatRelativeLabel(stats.lastDeployAt) : "—"}
                accent="text-status-live"
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
              <Card>
                <CardHeader title="Deploy activity" action="Last 14 days" />
                <div className="mt-4">
                  <BarChart
                    data={stats.perDay}
                    index="date"
                    categories={["deploys"]}
                    categoryLabels={{ deploys: "Deploys" }}
                    colors={["var(--chart-1)"]}
                    showLegend={false}
                    emptyMessage="No deploys in this window."
                  />
                </div>
              </Card>
              <Card>
                <CardHeader title="Status breakdown" />
                <div className="mt-4">
                  <DonutChart
                    data={stats.statusBreakdown}
                    colors={["var(--status-ok)", "var(--status-err)", "var(--status-warn)"]}
                    centerValue={stats.total}
                    centerLabel="deploys"
                  />
                </div>
              </Card>
            </div>
          </>
        )}
      </section>

      {/* ── Web analytics (Umami) — shown when connected ── */}
      <section className="space-y-4">
        <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Web analytics
        </h2>
        <WebAnalytics analytics={analytics} />
      </section>
    </div>
  )
}

function WebAnalytics({ analytics }: { analytics: ProjectAnalytics | null }) {
  if (!analytics || !analytics.configured) {
    return (
      <EmptyState
        title="Analytics isn't connected yet"
        description="A platform admin can connect a self-hosted Umami instance (set UMAMI_URL) to light up traffic, visitor, and referrer metrics here."
      />
    )
  }

  if (!analytics.ready) {
    return (
      <EmptyState
        title="Analytics not available for this project"
        description={analytics.reason || "This project can't be attached to analytics yet."}
      />
    )
  }

  const { summary } = analytics
  // Pre-slice the x-axis dates here (server) so we don't pass a formatter function
  // across the server→client boundary into the chart.
  const chartData = analytics.series.map((p) => ({
    date: p.date.slice(5),
    pageviews: p.pageviews,
    sessions: p.sessions,
  }))

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={faUsers} label="Visitors" value={summary.visitors} accent="text-status-live" />
        <StatCard icon={faChartBar} label="Pageviews" value={summary.pageviews} accent="text-status-ok" />
        <StatCard
          icon={faGaugeHigh}
          label="Bounce rate"
          value={`${summary.bounce_rate}%`}
          accent="text-status-warn"
        />
        <StatCard
          icon={faHourglassHalf}
          label="Avg. visit"
          value={fmtDuration(summary.avg_seconds)}
          accent="text-primary"
        />
      </div>

      <Card>
        <CardHeader title="Traffic" action={`Last ${analytics.period}`} />
        <div className="mt-4">
          <AreaChart
            data={chartData}
            index="date"
            categories={["pageviews", "sessions"]}
            categoryLabels={{ pageviews: "Pageviews", sessions: "Sessions" }}
            colors={["var(--chart-2)", "var(--chart-1)"]}
            emptyMessage="No traffic recorded in this window."
          />
        </div>
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Top pages" />
          <div className="mt-4">
            {analytics.top_pages.length === 0 ? (
              <p className="text-sm text-muted-foreground">No page data yet.</p>
            ) : (
              <BarList data={analytics.top_pages.map((p) => ({ name: p.label, value: p.count }))} />
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Top referrers" />
          <div className="mt-4">
            {analytics.top_referrers.length === 0 ? (
              <p className="text-sm text-muted-foreground">No referrer data yet.</p>
            ) : (
              <BarList
                data={analytics.top_referrers.map((r) => ({ name: r.label, value: r.count }))}
              />
            )}
          </div>
        </Card>
      </section>

      {analytics.tracking_snippet ? (
        <Card>
          <CardHeader title="Tracking snippet" action="Add to your site's <head>" />
          <pre className="mt-4 overflow-x-auto rounded-xl border border-border bg-black/60 p-4 font-mono text-xs text-zinc-300">
            {analytics.tracking_snippet}
          </pre>
        </Card>
      ) : null}
    </div>
  )
}
