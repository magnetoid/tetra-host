import { PlanForm } from "@/components/plans/plan-form"
import { PlansTable } from "@/components/plans/plans-table"
import { Card, CardHeader } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { Plan } from "@/lib/types"

export default async function PlansPage() {
  const session = await requireConsoleSession()

  if (session.admin.role !== "platform_admin") {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Platform billing"
          title="Plans"
          description="Manage subscription plans available to tenants."
        />
        <Card>
          <p className="text-sm text-zinc-400">
            Plan management is restricted to platform administrators.
          </p>
        </Card>
      </div>
    )
  }

  const plans = await fetchBackend<Plan[]>("/plans?include_archived=true", {
    token: session.token,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform billing"
        title="Plans"
        description="Create and manage subscription plans for tenants. Platform-admin only."
      />

      <Card>
        <CardHeader title="Create plan" />
        <div className="mt-4">
          <PlanForm />
        </div>
      </Card>

      <Card>
        <CardHeader
          title="All plans"
          action={`${plans.length} plan${plans.length === 1 ? "" : "s"}`}
        />
        <div className="mt-4">
          <PlansTable plans={plans} />
        </div>
      </Card>
    </div>
  )
}
