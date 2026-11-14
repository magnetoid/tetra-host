import { ServicePlacement } from "@/components/workspace/service-placement"
import { requireConsoleSession } from "@/lib/auth"
import { teamRef } from "@/lib/workspace"

export default async function DatabaseLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ id: string }>
}) {
  const session = await requireConsoleSession()
  const { id } = await params
  return (
    <div className="space-y-6">
      <ServicePlacement token={session.token} team={teamRef(session.admin)} databaseId={decodeURIComponent(id)} />
      {children}
    </div>
  )
}
