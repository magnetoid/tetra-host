"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { faPlus, faSliders, faTrash } from "@/lib/icons"
import type { Plan } from "@/lib/types"

type Mode = "create" | "edit"

type PlanFormProps = {
  /** When provided, the form operates in edit mode (PATCH). When absent, it creates (POST). */
  plan?: Plan
  onDone?: () => void
}

type FormState = {
  key: string
  name: string
  description: string
  price_cents: string
  currency: string
  max_apps: string
  max_domains: string
  cpu_millicores: string
  mem_mb: string
  disk_mb: string
  sort_order: string
}

function initState(plan?: Plan): FormState {
  return {
    key: plan?.key ?? "",
    name: plan?.name ?? "",
    description: plan?.description ?? "",
    price_cents: String(plan?.price_cents ?? 0),
    currency: plan?.currency ?? "usd",
    max_apps: String(plan?.max_apps ?? 1),
    max_domains: String(plan?.max_domains ?? 1),
    cpu_millicores: String(plan?.cpu_millicores ?? 500),
    mem_mb: String(plan?.mem_mb ?? 512),
    disk_mb: String(plan?.disk_mb ?? 5120),
    sort_order: String(plan?.sort_order ?? 0),
  }
}

function fieldClass(extra?: string) {
  return [
    "w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground",
    "placeholder:text-muted-foreground focus:border-primary focus:outline-none",
    extra,
  ]
    .filter(Boolean)
    .join(" ")
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-muted-foreground">{children}</label>
}

export function PlanForm({ plan, onDone }: PlanFormProps) {
  const mode: Mode = plan ? "edit" : "create"
  const router = useRouter()
  const [fields, setFields] = useState<FormState>(() => initState(plan))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function set(key: keyof FormState, value: string) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const url = mode === "create" ? "/api/proxy/plans" : `/api/proxy/plans/${plan!.id}`
      const method = mode === "create" ? "POST" : "PATCH"

      const body =
        mode === "create"
          ? {
              key: fields.key,
              name: fields.name,
              description: fields.description,
              price_cents: Number(fields.price_cents),
              currency: fields.currency,
              max_apps: Number(fields.max_apps),
              max_domains: Number(fields.max_domains),
              cpu_millicores: Number(fields.cpu_millicores),
              mem_mb: Number(fields.mem_mb),
              disk_mb: Number(fields.disk_mb),
              sort_order: Number(fields.sort_order),
            }
          : {
              name: fields.name || undefined,
              description: fields.description || undefined,
              price_cents: fields.price_cents !== "" ? Number(fields.price_cents) : undefined,
              currency: fields.currency || undefined,
              max_apps: fields.max_apps !== "" ? Number(fields.max_apps) : undefined,
              max_domains: fields.max_domains !== "" ? Number(fields.max_domains) : undefined,
              cpu_millicores:
                fields.cpu_millicores !== "" ? Number(fields.cpu_millicores) : undefined,
              mem_mb: fields.mem_mb !== "" ? Number(fields.mem_mb) : undefined,
              disk_mb: fields.disk_mb !== "" ? Number(fields.disk_mb) : undefined,
              sort_order: fields.sort_order !== "" ? Number(fields.sort_order) : undefined,
            }

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        let detail = res.statusText
        try {
          const payload = (await res.json()) as { detail?: string }
          if (payload.detail) {
            detail = payload.detail
          }
        } catch {
          // keep statusText
        }
        setError(detail)
        return
      }

      router.refresh()
      onDone?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  async function handleArchive() {
    if (!plan) return
    setError(null)
    setBusy(true)
    try {
      const res = await fetch(`/api/proxy/plans/${plan.id}/archive`, { method: "POST" })
      if (!res.ok) {
        let detail = res.statusText
        try {
          const payload = (await res.json()) as { detail?: string }
          if (payload.detail) detail = payload.detail
        } catch {
          // keep statusText
        }
        setError(detail)
        return
      }
      router.refresh()
      onDone?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {mode === "create" && (
          <div className="space-y-1.5">
            <Label>Key *</Label>
            <input
              aria-label="Plan key"
              required
              value={fields.key}
              onChange={(e) => set("key", e.target.value)}
              placeholder="starter"
              className={fieldClass()}
            />
          </div>
        )}

        <div className="space-y-1.5">
          <Label>Name *</Label>
          <input
            aria-label="Plan name"
            required
            value={fields.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="Starter Plan"
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5 sm:col-span-2">
          <Label>Description</Label>
          <input
            aria-label="Plan description"
            value={fields.description}
            onChange={(e) => set("description", e.target.value)}
            placeholder="A brief description of what this plan includes"
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Price (cents)</Label>
          <input
            aria-label="Price cents"
            type="number"
            min={0}
            value={fields.price_cents}
            onChange={(e) => set("price_cents", e.target.value)}
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Currency</Label>
          <input
            aria-label="Currency"
            value={fields.currency}
            onChange={(e) => set("currency", e.target.value)}
            placeholder="usd"
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Max apps</Label>
          <input
            aria-label="Max apps"
            type="number"
            min={0}
            value={fields.max_apps}
            onChange={(e) => set("max_apps", e.target.value)}
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Max domains</Label>
          <input
            aria-label="Max domains"
            type="number"
            min={0}
            value={fields.max_domains}
            onChange={(e) => set("max_domains", e.target.value)}
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>CPU (millicores)</Label>
          <input
            aria-label="CPU millicores"
            type="number"
            min={0}
            value={fields.cpu_millicores}
            onChange={(e) => set("cpu_millicores", e.target.value)}
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Memory (MB)</Label>
          <input
            aria-label="Memory MB"
            type="number"
            min={0}
            value={fields.mem_mb}
            onChange={(e) => set("mem_mb", e.target.value)}
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Disk (MB)</Label>
          <input
            aria-label="Disk MB"
            type="number"
            min={0}
            value={fields.disk_mb}
            onChange={(e) => set("disk_mb", e.target.value)}
            className={fieldClass()}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Sort order</Label>
          <input
            aria-label="Sort order"
            type="number"
            value={fields.sort_order}
            onChange={(e) => set("sort_order", e.target.value)}
            className={fieldClass()}
          />
        </div>
      </div>

      {error ? (
        <p role="alert" className="rounded-lg bg-status-err/10 px-3 py-2 text-sm text-status-err">
          {error}
        </p>
      ) : null}

      <div className="flex items-center gap-3">
        <Button
          type="submit"
          variant="primary"
          icon={mode === "create" ? faPlus : faSliders}
          disabled={busy}
        >
          {mode === "create" ? "Create plan" : "Save changes"}
        </Button>

        {mode === "edit" && !plan?.is_archived && (
          <Button
            type="button"
            variant="danger"
            icon={faTrash}
            disabled={busy}
            onClick={handleArchive}
          >
            Archive
          </Button>
        )}

        {onDone && (
          <Button type="button" variant="ghost" disabled={busy} onClick={onDone}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
