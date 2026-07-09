import { AiReseller } from "@/components/marketplace/ai-reseller"
import { CloudflareReseller } from "@/components/marketplace/cloudflare-reseller"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { AiKey, AiModel, DNSResponse, ResellableService } from "@/lib/types"

export const metadata = { title: "Marketplace" }

const EMPTY_DNS: DNSResponse = { providers: [], zones: [], records: [], selected_zone: "" }

export default async function MarketplacePage() {
  const session = await requireConsoleSession()
  const token = { token: session.token }

  const [models, keys, services, dns] = await Promise.all([
    fetchBackend<AiModel[]>("/ai/models", token).catch(() => [] as AiModel[]),
    fetchBackend<AiKey[]>("/ai/keys", token).catch(() => [] as AiKey[]),
    fetchBackend<ResellableService[]>("/cloudflare/services", token).catch(() => [] as ResellableService[]),
    fetchBackend<DNSResponse>("/dns", token).catch(() => EMPTY_DNS),
  ])

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Reseller"
        title="Marketplace"
        description="Resell Cloudflare plans & services and AI models to your workspace."
        action={<RefreshLink href="/marketplace" label="Refresh" />}
      />

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">AI models</h2>
        <AiReseller models={models} keys={keys} />
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Cloudflare</h2>
        <CloudflareReseller services={services} zones={dns.zones} />
      </section>
    </div>
  )
}
