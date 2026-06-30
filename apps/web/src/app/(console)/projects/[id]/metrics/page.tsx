import { AreaChart, type AreaPoint } from "@/components/charts/area-chart"
import { BarList } from "@/components/charts/bar-list"
import { Card, CardHeader } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { faChartBar, faGaugeHigh, faHourglassHalf, faUsers } from "@/lib/icons"
import type { ProjectAnalytics } from "@/lib/types"

function fmtDuration(seconds: number): string {
  if (!seconds) return "0s"
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m ? `${m}m ${s}s` : `${s}s`
}

export default async function MetricsPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await requireConsoleSession()
  const { id } = await params

  const analytics = await fetchBackend<ProjectAnalytics>(
    `/projects/${id}/analytics?period=7d`,
    { token: session.token },
  ).catch(() => null)

  const header = (
    <PageHeader
      eyebrow="Observability"
      title="Metrics"
      description="Privacy-first web analytics for this project, powered by Umami."
    />
  )

  if (!analytics || !analytics.configured) {
    return (
      <div className="space-y-6">
        {header}
        <EmptyState
          title="Analytics isn't connected yet"
          description="A platform admin can connect a self-hosted Umami instance (set UMAMI_URL) to light up traffic, visitor, and referrer metrics here."
        />
      </div>
    )
  }

  if (!analytics.ready) {
    return (
      <div className="space-y-6">
        {header}
        <EmptyState
          title="Analytics not available for this project"
          description={analytics.reason || "This project can't be attached to analytics yet."}
        />
      </div>
    )
  }

  const { summary } = analytics
  const chartData: AreaPoint[] = analytics.series.map((p) => ({
    date: p.date,
    pageviews: p.pageviews,
    sessions: p.sessions,
  }))

  return (
    <div className="space-y-6">
      {header}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={faUsers} label="Visitors" value={summary.visitors} accent="text-sky-400" />
        <StatCard icon={faChartBar} label="Pageviews" value={summary.pageviews} accent="text-emerald-400" />
        <StatCard icon={faGaugeHigh} label="Bounce rate" value={`${summary.bounce_rate}%`} accent="text-amber-400" />
        <StatCard
          icon={faHourglassHalf}
          label="Avg. visit"
          value={fmtDuration(summary.avg_seconds)}
          accent="text-violet-400"
        />
      </section>

      <Card>
        <CardHeader title="Traffic" action={`Last ${analytics.period}`} />
        <div className="mt-4">
          <AreaChart
            data={chartData}
            series={[
              { key: "pageviews", label: "Pageviews", color: "#38bdf8" },
              { key: "sessions", label: "Sessions", color: "#a78bfa" },
            ]}
          />
        </div>
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Top pages" />
          <div className="mt-4">
            {analytics.top_pages.length === 0 ? (
              <p className="text-sm text-zinc-500">No page data yet.</p>
            ) : (
              <BarList data={analytics.top_pages.map((p) => ({ name: p.label, value: p.count }))} />
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Top referrers" />
          <div className="mt-4">
            {analytics.top_referrers.length === 0 ? (
              <p className="text-sm text-zinc-500">No referrer data yet.</p>
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
