import { TeamManager } from "@/components/team/team-manager"
import { PageHeader, RefreshLink } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { TeamResponse } from "@/lib/types"

export default async function TeamPage() {
  const session = await requireConsoleSession()
  const team = await fetchBackend<TeamResponse>("/team", { token: session.token }).catch(
    () => ({ members: [], invites: [] }) as TeamResponse,
  )

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
    </div>
  )
}
