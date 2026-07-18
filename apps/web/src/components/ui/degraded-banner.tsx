import { AlertBanner } from "@/components/ui/alert-banner"

/**
 * Standard "some data on this page is stale/missing" banner. Renders nothing
 * when every source loaded — pages pass `degradedSources(results)` directly.
 */
export function DegradedBanner({ sources }: { sources: string[] }) {
  if (sources.length === 0) return null
  return (
    <AlertBanner tone="error">
      Could not load: {sources.join(", ")}. Data on this page may be incomplete — retry with a
      refresh.
    </AlertBanner>
  )
}
