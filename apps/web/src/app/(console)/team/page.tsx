import { headers } from "next/headers"

import { SSOSettings } from "@/components/sso/sso-settings"
import { TeamManager } from "@/components/team/team-manager"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { SSOConfig, TeamResponse } from "@/lib/types"

export default async function TeamPage() {
  const session = await requireConsoleSession()
  const headerList = await headers()
  const host = headerList.get("x-forwarded-host") ?? headerList.get("host") ?? "localhost"
  const proto = headerList.get("x-forwarded-proto") ?? "https"
  const origin = `${proto}://${host}`
  const isOwner =
    session.admin.role === "owner" || session.admin.role === "platform_admin"
  const team = await fetchBackend<TeamResponse>("/team", { token: session.token }).catch(
    () => ({ members: [], invites: [] }) as TeamResponse,
  )
  // Owner-only: SSO config (the endpoint 403s for non-owners → null → card hidden).
  const sso = isOwner
    ? await fetchBackend<SSOConfig>("/sso", { token: session.token }).catch(() => null)
    : null

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Access"
        title="Team"
        description="Invite teammates with a share link and control their access. Members join your tenant with the role you assign."
        action={<RefreshLink href="/team" label="Refresh" />}
      />
      <TeamManager
        team={team}
        currentRole={session.admin.role ?? ""}
        currentAdminId={session.admin.id}
      />
      {sso ? (
        <SSOSettings
          config={sso}
          tenantSlug={session.admin.tenant_slug ?? ""}
          origin={origin}
        />
      ) : null}
    </div>
  )
}
