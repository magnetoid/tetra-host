import Link from "next/link"

import { AccountSettingsForm } from "@/components/account/account-settings-form"
import { ApiTokensManager } from "@/components/account/api-tokens-manager"
import { TwoFactorManager } from "@/components/account/two-factor-manager"
import { Card, CardHeader } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { requireConsoleSession } from "@/lib/auth"
import { fetchDegraded } from "@/lib/fetch-degraded"
import type { ApiTokenSummary, TwoFactorStatus } from "@/lib/types"

export const metadata = { title: "Account" }

export default async function AccountPage() {
  const { admin, token } = await requireConsoleSession()
  const tokensRes = await fetchDegraded<ApiTokenSummary[]>("/account/tokens", "API tokens", [], {
    token,
  })
  const twoFactorRes = await fetchDegraded<TwoFactorStatus>(
    "/account/2fa",
    "Two-factor auth",
    { enabled: false, backup_codes_remaining: 0 },
    { token },
  )
  const isPlatformAdmin = admin.role === "platform_admin"
  const initial = (admin.full_name || admin.email || "?").charAt(0).toUpperCase()

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Your profile" title="Account" description="Your profile and workspace." />

      <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="grid h-14 w-14 place-items-center rounded-full bg-primary text-lg font-bold text-white">
            {initial}
          </div>
          <div>
            <div className="text-lg font-medium">{admin.full_name}</div>
            <div className="font-mono text-sm text-muted-foreground">{admin.email}</div>
          </div>
          {isPlatformAdmin ? (
            <span className="ml-auto rounded-full border border-primary/50 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              Platform admin
            </span>
          ) : null}
        </div>

        <dl className="mt-6 grid grid-cols-1 gap-4 border-t border-border pt-6 sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Workspace</dt>
            <dd className="mt-1 text-sm">{admin.tenant_name || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Role</dt>
            <dd className="mt-1 text-sm capitalize">{(admin.role || "member").replace("_", " ")}</dd>
          </div>
        </dl>
      </div>

      {isPlatformAdmin ? (
        <Link
          href="/super-admin"
          className="flex items-center justify-between rounded-lg border border-border bg-card p-5 shadow-sm transition-colors hover:bg-accent"
        >
          <div>
            <div className="font-medium">Super Admin</div>
            <div className="text-sm text-muted-foreground">
              Tenants, plans, resources and platform administration.
            </div>
          </div>
          <span className="text-muted-foreground">→</span>
        </Link>
      ) : null}

      <AccountSettingsForm fullName={admin.full_name} email={admin.email} />

      <Card>
        <CardHeader
          title="Two-factor authentication"
          action="A time-based code (TOTP) on every sign-in — panel, console, and CLI. Optional, off by default."
        />
        <div className="mt-4">
          <TwoFactorManager status={twoFactorRes.data} />
        </div>
      </Card>

      <Card>
        <CardHeader
          title="API tokens"
          action="Personal tokens for the tetra CLI and CI — Bearer-authenticated, revocable."
        />
        <div className="mt-4">
          <ApiTokensManager tokens={tokensRes.data} />
        </div>
      </Card>
    </div>
  )
}
