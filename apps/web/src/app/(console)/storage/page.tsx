import { StorageManager } from "@/components/storage/storage-manager"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { BucketRecord, StorageStatus } from "@/lib/types"

const OFFLINE: StorageStatus = { configured: false, can_issue_credentials: false, endpoint: "" }

export default async function StoragePage() {
  const session = await requireConsoleSession()

  const [bucketsRes, statusRes] = await Promise.all([
    fetchDegraded<BucketRecord[]>("/storage/buckets", "Storage buckets", [], {
      token: session.token,
    }),
    fetchDegraded<StorageStatus>("/storage/status", "Storage status", OFFLINE, {
      token: session.token,
    }),
  ])
  const buckets = bucketsRes.data
  const status = statusRes.data

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Data"
        title="Object storage"
        description="S3-compatible buckets on Cloudflare R2 — zero egress fees. Provision buckets and hand out scoped credentials."
      />
      <DegradedBanner sources={degradedSources([bucketsRes, statusRes])} />
      <StorageManager buckets={buckets} status={status} />
    </div>
  )
}
