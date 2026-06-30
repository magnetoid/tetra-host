import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { faBug } from "@/lib/icons"

export default function ErrorsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Observability"
        title="Errors"
        description="Runtime errors and exceptions captured for this project."
      />

      <Card className="flex flex-col items-center gap-4 py-16 text-center">
        <FontAwesomeIcon icon={faBug} className="h-12 w-12 text-zinc-600" />
        <div>
          <h3 className="text-lg font-semibold text-zinc-300">Error tracking coming soon</h3>
          <p className="mt-1 text-sm text-zinc-500">
            Runtime errors and exceptions will surface here once error tracking is wired up.
          </p>
        </div>
      </Card>
    </div>
  )
}
