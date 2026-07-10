import { JobsManager } from "@/components/jobs/jobs-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ScheduledJobRecord } from "@/lib/types"

export default async function JobsPage() {
  const session = await requireConsoleSession()

  const jobs = await fetchBackend<ScheduledJobRecord[]>("/jobs", { token: session.token }).catch(
    () => [] as ScheduledJobRecord[],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Automation"
        title="Scheduled jobs"
        description="Cron-triggered HTTP calls — ping an endpoint on a schedule. The platform runs them for you and records each run."
      />
      <JobsManager jobs={jobs} />
    </div>
  )
}
