import { AiReseller } from "@/components/marketplace/ai-reseller"
import { CloudflareReseller } from "@/components/marketplace/cloudflare-reseller"
import { DegradedBanner } from "@/components/ui/degraded-banner"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { degradedSources, fetchDegraded } from "@/lib/fetch-degraded"
import type { AiKey, AiModel, DNSResponse, ResellableService } from "@/lib/types"

export const metadata = { title: "Add-ons" }

const EMPTY_DNS: DNSResponse = { providers: [], zones: [], records: [], selected_zone: "" }

export default async function MarketplacePage() {
  const session = await requireConsoleSession()
  const token = { token: session.token }

  const [modelsRes, keysRes, servicesRes, dnsRes] = await Promise.all([
    fetchDegraded<AiModel[]>("/ai/models", "AI models", [], token),
    fetchDegraded<AiKey[]>("/ai/keys", "AI keys", [], token),
    fetchDegraded<ResellableService[]>("/cloudflare/services", "Cloudflare services", [], token),
    fetchDegraded<DNSResponse>("/dns", "DNS", EMPTY_DNS, token),
  ])
  const models = modelsRes.data
  const keys = keysRes.data
  const services = servicesRes.data
  const dns = dnsRes.data

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Reseller"
        title="Add-ons"
        description="Paid services & plans for your workspace — Cloudflare plans, security add-ons, and AI models. (For deployable container apps, see the App catalog.)"
        action={<RefreshLink href="/marketplace" label="Refresh" />}
      />

      <DegradedBanner sources={degradedSources([modelsRes, keysRes, servicesRes, dnsRes])} />

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
