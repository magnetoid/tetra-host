import { ServicePlacement } from "@/components/workspace/service-placement"
import { requireConsoleSession } from "@/lib/auth"
import { teamRef } from "@/lib/workspace"

export default async function AppLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ project: string }>
}) {
  const session = await requireConsoleSession()
  const { project } = await params
  return (
    <div className="space-y-6">
      <ServicePlacement token={session.token} team={teamRef(session.admin)} stack={decodeURIComponent(project)} />
      {children}
    </div>
  )
}
