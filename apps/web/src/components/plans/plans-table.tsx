"use client"

import { useState } from "react"

import { PlanForm } from "@/components/plans/plan-form"
import { Button } from "@/components/ui/button"
import { faSliders } from "@/lib/icons"
import type { Plan } from "@/lib/types"

function formatPrice(cents: number, currency: string) {
  if (cents === 0) return "Free"
  const dollars = cents / 100
  return `${currency.toUpperCase()} $${dollars.toFixed(2)}`
}

function ResourceBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300">
      <span className="text-zinc-500">{label}</span>
      {value}
    </span>
  )
}

export function PlansTable({ plans }: { plans: Plan[] }) {
  const [editingId, setEditingId] = useState<string | null>(null)

  if (plans.length === 0) {
    return <p className="text-sm text-zinc-500">No plans yet. Create one above.</p>
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-background/60 text-left text-zinc-500">
          <tr>
            <th className="px-4 py-3 font-medium">Key</th>
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Price</th>
            <th className="px-4 py-3 font-medium">Apps / Domains</th>
            <th className="px-4 py-3 font-medium">Resources</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-background">
          {plans.map((plan) =>
            editingId === plan.id ? (
              <tr key={plan.id}>
                <td colSpan={7} className="p-4">
                  <div className="mb-2 text-sm font-medium text-zinc-300">
                    Editing: {plan.name}
                  </div>
                  <PlanForm plan={plan} onDone={() => setEditingId(null)} />
                </td>
              </tr>
            ) : (
              <tr key={plan.id} className={plan.is_archived ? "opacity-50" : undefined}>
                <td className="px-4 py-3 font-mono text-xs text-zinc-400">{plan.key}</td>
                <td className="px-4 py-3">
                  <div className="font-medium">{plan.name}</div>
                  {plan.description ? (
                    <div className="text-xs text-zinc-500">{plan.description}</div>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-zinc-300">
                  {formatPrice(plan.price_cents, plan.currency)}
                </td>
                <td className="px-4 py-3 text-zinc-400">
                  {plan.max_apps} / {plan.max_domains}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    <ResourceBadge label="CPU" value={`${plan.cpu_millicores}m`} />
                    <ResourceBadge label="Mem" value={`${plan.mem_mb}MB`} />
                    <ResourceBadge label="Disk" value={`${plan.disk_mb}MB`} />
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={
                      plan.is_archived
                        ? "text-xs text-zinc-500"
                        : "text-xs font-medium text-green-400"
                    }
                  >
                    {plan.is_archived ? "Archived" : "Active"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={faSliders}
                    onClick={() => setEditingId(plan.id)}
                  >
                    Edit
                  </Button>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </div>
  )
}
