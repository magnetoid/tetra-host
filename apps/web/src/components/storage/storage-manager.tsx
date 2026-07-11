"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { faPlus, faTrash } from "@/lib/icons"
import type { BucketCreated, BucketRecord, StorageStatus } from "@/lib/types"

const INPUT =
  "rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

export function StorageManager({
  buckets,
  status,
}: {
  buckets: BucketRecord[]
  status: StorageStatus
}) {
  const router = useRouter()
  const [name, setName] = useState("")
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Credentials are returned exactly once on create — surface them until dismissed.
  const [created, setCreated] = useState<BucketCreated | null>(null)

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending("create")
    setError(null)
    try {
      const res = await fetch("/api/proxy/storage/buckets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      })
      const payload = (await res.json().catch(() => ({}))) as BucketCreated & { detail?: string }
      if (!res.ok) {
        setError(payload.detail ?? "Bucket creation failed.")
        return
      }
      setName("")
      if (payload.secret_access_key) setCreated(payload)
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  async function remove(bucketName: string) {
    setPending(`rm:${bucketName}`)
    setError(null)
    try {
      const res = await fetch(`/api/proxy/storage/buckets/${bucketName}`, { method: "DELETE" })
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string }
        setError(p.detail ?? "Delete failed.")
        return
      }
      router.refresh()
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(null)
    }
  }

  if (!status.configured) {
    return (
      <EmptyState
        title="Object storage isn't configured"
        description="A platform admin connects Cloudflare R2 (set CLOUDFLARE_ACCOUNT_ID + an R2-scoped token) to offer S3-compatible buckets here."
        action={
          <Link
            href="/docs"
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-accent"
          >
            Read the storage setup guide →
          </Link>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {created ? (
        <div className="space-y-2 rounded-2xl border border-primary/40 bg-primary/5 p-4">
          <div className="text-sm font-medium">
            Bucket <span className="font-mono">{created.name}</span> created — save these credentials now
            (shown once):
          </div>
          <dl className="grid gap-2 font-mono text-xs">
            <CredRow label="Endpoint" value={created.endpoint} />
            <CredRow label="Access Key ID" value={created.access_key_id} />
            <CredRow label="Secret Access Key" value={created.secret_access_key} />
          </dl>
          <Button size="sm" onClick={() => setCreated(null)}>
            I saved them
          </Button>
        </div>
      ) : null}

      <form
        onSubmit={create}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-muted p-4"
      >
        <label className="block flex-1 text-sm">
          <span className="mb-2 block text-muted-foreground">New bucket</span>
          <input
            aria-label="New bucket"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="assets"
            className={`${INPUT} w-full`}
            required
          />
        </label>
        <Button type="submit" icon={faPlus} disabled={pending !== null || !name}>
          {pending === "create" ? "…" : "Create bucket"}
        </Button>
      </form>

      {!status.can_issue_credentials ? (
        <AlertBanner tone="info">
          Buckets are created, but S3 credentials aren&apos;t auto-issued yet — configure the R2
          permission group to hand tenants scoped keys.
        </AlertBanner>
      ) : null}

      {buckets.length === 0 ? (
        <EmptyState
          title="No buckets yet"
          description="Create an S3-compatible R2 bucket above. Zero egress fees."
        />
      ) : (
        <div className="space-y-3">
          {buckets.map((b) => (
            <div
              key={b.name}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-muted p-4"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">{b.name}</div>
                <div className="truncate font-mono text-xs text-muted-foreground">{b.endpoint}</div>
              </div>
              <Button
                size="sm"
                icon={faTrash}
                disabled={pending !== null}
                onClick={() => remove(b.name)}
              >
                {pending === `rm:${b.name}` ? "…" : "Delete"}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CredRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <dt className="w-32 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 flex-1 truncate rounded-md border border-border bg-background px-2 py-1">
        {value || "—"}
      </dd>
    </div>
  )
}
