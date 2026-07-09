"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { faCircleCheck, faPlus } from "@/lib/icons"
import type { CloudflarePlan, DNSZoneRecord, ResellableService, ZoneSubscription } from "@/lib/types"

const FIELD =
  "rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none"

const CATEGORY_LABEL: Record<string, string> = {
  plan: "Plans",
  security: "Security",
  performance: "Performance",
  developer: "Developer",
}

async function readError(res: Response): Promise<string> {
  try {
    const p = (await res.json()) as { detail?: string }
    if (p.detail) return p.detail
  } catch {
    /* keep statusText */
  }
  return res.statusText
}

export function CloudflareReseller({
  services,
  zones,
  billingEnabled = false,
}: {
  services: ResellableService[]
  zones: DNSZoneRecord[]
  /** When false, paid activations (plans + usage-billed toggles) are disabled — the
   *  backend hard-blocks them too (reseller_cloudflare_billing_enabled). */
  billingEnabled?: boolean
}) {
  const router = useRouter()
  const [zoneId, setZoneId] = useState(zones[0]?.id ?? "")
  const [plans, setPlans] = useState<CloudflarePlan[]>([])
  const [subscription, setSubscription] = useState<ZoneSubscription | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const loadZone = useCallback(async (id: string) => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [plansRes, subRes] = await Promise.all([
        fetch(`/api/proxy/cloudflare/zones/${id}/plans`),
        fetch(`/api/proxy/cloudflare/zones/${id}/subscription`),
      ])
      setPlans(plansRes.ok ? ((await plansRes.json()) as CloudflarePlan[]) : [])
      setSubscription(subRes.ok ? ((await subRes.json()) as ZoneSubscription) : null)
      if (!plansRes.ok) setError(await readError(plansRes))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    // Defer so no setState runs during the effect's synchronous phase.
    queueMicrotask(() => {
      if (alive) void loadZone(zoneId)
    })
    return () => {
      alive = false
    }
  }, [zoneId, loadZone])

  async function activatePlan(ratePlanId: string) {
    setBusy(`plan:${ratePlanId}`)
    setError(null)
    setNotice(null)
    try {
      const res = await fetch(`/api/proxy/cloudflare/zones/${zoneId}/subscription`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rate_plan_id: ratePlanId, frequency: "monthly" }),
      })
      if (!res.ok) {
        setError(await readError(res))
        return
      }
      setNotice(`Activated the ${ratePlanId} plan.`)
      await loadZone(zoneId)
      router.refresh()
    } finally {
      setBusy(null)
    }
  }

  async function activateService(key: string) {
    setBusy(`svc:${key}`)
    setError(null)
    setNotice(null)
    try {
      const res = await fetch(`/api/proxy/cloudflare/zones/${zoneId}/services/${key}/activate`, {
        method: "POST",
      })
      const payload = (await res.json().catch(() => ({}))) as { detail?: string; note?: string }
      if (!res.ok) {
        setError(payload.detail ?? "Activation failed.")
        return
      }
      setNotice(payload.note ?? "Service activated.")
      await loadZone(zoneId)
      router.refresh()
    } finally {
      setBusy(null)
    }
  }

  if (zones.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No Cloudflare zones assigned to this tenant yet — add one in DNS to resell plans and services on it.
      </p>
    )
  }

  const categories = ["plan", "security", "performance", "developer"]

  return (
    <div className="space-y-6">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      {notice ? <AlertBanner tone="success">{notice}</AlertBanner> : null}
      {!billingEnabled ? (
        <AlertBanner tone="info">
          Paid activation is disabled on this platform — no real charges are made. You can browse
          plans and services; activation turns on once billing is live.
        </AlertBanner>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-muted-foreground">Zone</label>
        <select
          aria-label="Zone"
          value={zoneId}
          onChange={(e) => setZoneId(e.target.value)}
          className={FIELD}
        >
          {zones.map((z) => (
            <option key={z.id} value={z.id}>
              {z.name}
            </option>
          ))}
        </select>
        {subscription?.rate_plan_id ? (
          <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            current: {subscription.rate_plan_id} ({subscription.state})
          </span>
        ) : null}
      </div>

      {/* Plans */}
      <div>
        <h3 className="mb-3 text-base font-medium">Plans</h3>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading plans…</p>
        ) : plans.length === 0 ? (
          <p className="text-sm text-muted-foreground">No plans available for this zone.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {plans.map((p) => (
              <div key={p.id} className="flex flex-col gap-2 rounded-2xl border border-border bg-muted/40 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{p.name || p.id}</span>
                  {p.is_subscribed ? (
                    <span className="text-xs text-status-ok">current</span>
                  ) : null}
                </div>
                <div className="font-mono text-sm text-muted-foreground">
                  {p.price} {p.currency}/{p.frequency}
                </div>
                <Button
                  variant={p.is_subscribed ? "secondary" : "primary"}
                  icon={p.is_subscribed ? faCircleCheck : faPlus}
                  disabled={p.is_subscribed || !p.can_subscribe || busy !== null || !billingEnabled}
                  onClick={() => activatePlan(p.id)}
                  className="mt-auto"
                >
                  {p.is_subscribed ? "Active" : busy === `plan:${p.id}` ? "Activating…" : "Activate"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Services */}
      <div>
        <h3 className="mb-3 text-base font-medium">Services</h3>
        <div className="space-y-5">
          {categories.map((cat) => {
            const items = services.filter((s) => s.category === cat)
            if (items.length === 0) return null
            return (
              <div key={cat}>
                <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {CATEGORY_LABEL[cat] ?? cat}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {items.map((s) => (
                    <div
                      key={s.key}
                      className="flex items-center justify-between gap-3 rounded-xl border border-border bg-muted/40 p-3"
                    >
                      <div className="min-w-0">
                        <div className="font-medium">{s.name}</div>
                        <div className="text-xs text-muted-foreground">{s.description}</div>
                      </div>
                      <Button
                        size="sm"
                        variant="primary"
                        disabled={busy !== null || (!billingEnabled && s.activation !== "addon")}
                        onClick={() => activateService(s.key)}
                      >
                        {busy === `svc:${s.key}` ? "…" : "Activate"}
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
