import { StorageManager } from "@/components/storage/storage-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { BucketRecord, StorageStatus } from "@/lib/types"

const OFFLINE: StorageStatus = { configured: false, can_issue_credentials: false, endpoint: "" }

export default async function StoragePage() {
  const session = await requireConsoleSession()

  const [buckets, status] = await Promise.all([
    fetchBackend<BucketRecord[]>("/storage/buckets", { token: session.token }).catch(
      () => [] as BucketRecord[],
    ),
    fetchBackend<StorageStatus>("/storage/status", { token: session.token }).catch(() => OFFLINE),
  ])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Data"
        title="Object storage"
        description="S3-compatible buckets on Cloudflare R2 — zero egress fees. Provision buckets and hand out scoped credentials."
      />
      <StorageManager buckets={buckets} status={status} />
    </div>
  )
}
