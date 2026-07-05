import { StatusBadge } from "@/components/ui/status-badge"
import type { ProviderSummary } from "@/lib/types"

export function ProviderCard({ provider }: { provider: ProviderSummary }) {
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="font-medium">{provider.name}</div>
        <StatusBadge value={provider.status} />
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{provider.detail}</p>
    </div>
  )
}
