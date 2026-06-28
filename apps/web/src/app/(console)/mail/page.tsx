import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { ProviderCard } from "@/components/ui/provider-card"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { MailResponse } from "@/lib/types"
import { formatBytes } from "@/lib/utils"

type MailPageProps = {
  searchParams: Promise<{ refresh?: string }>
}

export default async function MailPage({ searchParams }: MailPageProps) {
  const session = await requireConsoleSession()
  const params = await searchParams
  const mail = await fetchBackend<MailResponse>("/mail", {
    token: session.token,
    searchParams: { refresh: params.refresh === "1" ? "1" : undefined },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Mailcow backend"
        title="Mail"
        description="Domain and mailbox inventory for the current Mailcow instance."
        action={<RefreshLink href="/mail?refresh=1" label="Refresh mail state" />}
      />

      {mail.providers.length > 0 ? (
        <section className="grid gap-3 md:grid-cols-3">
          {mail.providers.map((provider) => (
            <ProviderCard key={provider.name} provider={provider} />
          ))}
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Mail domains</h2>
            <span className="text-sm text-zinc-500">{mail.domains.length} total</span>
          </div>
          <div className="mt-4 space-y-3">
            {mail.domains.length > 0 ? (
              mail.domains.map((domain) => (
                <div key={domain.domain_name} className="rounded-xl border border-border bg-background p-4">
                  <div className="font-medium">{domain.domain_name}</div>
                  <div className="mt-1 text-sm text-zinc-500">
                    {domain.mailboxes} mailboxes · {domain.aliases} aliases
                  </div>
                </div>
              ))
            ) : (
              <EmptyState title="No domains returned." />
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent mailboxes</h2>
            <span className="text-sm text-zinc-500">{mail.mailboxes.length} shown</span>
          </div>
          <div className="mt-4 overflow-hidden rounded-2xl border border-border">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-background/60 text-left text-zinc-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Mailbox</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Quota</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-background">
                {mail.mailboxes.length > 0 ? (
                  mail.mailboxes.map((mailbox) => (
                    <tr key={mailbox.username}>
                      <td className="px-4 py-3">{mailbox.username}</td>
                      <td className="px-4 py-3 text-zinc-400">{mailbox.name || "Mailbox user"}</td>
                      <td className="px-4 py-3 text-zinc-400">{formatBytes(mailbox.quota_bytes)}</td>
                      <td className="px-4 py-3">
                        <StatusBadge value={mailbox.active ? "Active" : "Inactive"} />
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-zinc-500">
                      No mailboxes returned.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}
