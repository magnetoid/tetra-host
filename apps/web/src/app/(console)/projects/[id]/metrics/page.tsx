import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { faChartLine } from "@/lib/icons"

export default function MetricsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Observability"
        title="Metrics"
        description="CPU, memory, and request throughput for this project."
      />

      <Card className="flex flex-col items-center gap-4 py-16 text-center">
        <FontAwesomeIcon icon={faChartLine} className="h-12 w-12 text-zinc-600" />
        <div>
          <h3 className="text-lg font-semibold text-zinc-300">Metrics coming soon</h3>
          <p className="mt-1 text-sm text-zinc-500">
            Real-time resource usage charts will appear here once the metrics pipeline is ready.
          </p>
        </div>
      </Card>
    </div>
  )
}
