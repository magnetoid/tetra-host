"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { faWandSparkles } from "@/lib/icons"
import type { BuildDiagnosis } from "@/lib/types"

const CONFIDENCE_TONE: Record<string, string> = {
  high: "text-status-ok",
  medium: "text-status-warn",
  low: "text-muted-foreground",
}

/** Fetches and shows an AI/heuristic diagnosis for one deployment ("Explain"). */
export function ExplainButton({ deploymentId }: { deploymentId: string }) {
  const [diagnosis, setDiagnosis] = useState<BuildDiagnosis | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function explain() {
    setPending(true)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/deploys/${deploymentId}/explain`)
      const payload = (await response.json().catch(() => ({}))) as BuildDiagnosis & {
        detail?: string
      }
      if (!response.ok) {
        setError(payload.detail ?? "Could not diagnose this deployment.")
        return
      }
      setDiagnosis(payload)
    } catch {
      setError("Unable to reach the control plane.")
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="w-full">
      <Button size="sm" variant="ghost" icon={faWandSparkles} disabled={pending} onClick={explain}>
        {pending ? "Diagnosing…" : "Explain"}
      </Button>

      {error ? <p className="mt-2 text-sm text-status-err">{error}</p> : null}

      {diagnosis ? (
        <div className="mt-3 w-full rounded-lg border border-primary/25 bg-primary/10 p-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground">{diagnosis.summary}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>
              category <span className="font-mono text-muted-foreground">{diagnosis.category}</span>
            </span>
            <span>
              confidence{" "}
              <span className={CONFIDENCE_TONE[diagnosis.confidence] ?? "text-muted-foreground"}>
                {diagnosis.confidence}
              </span>
            </span>
            <span>
              via {diagnosis.source === "ai" ? "Claude" : "heuristics"}
            </span>
          </div>

          {diagnosis.likely_causes.length > 0 ? (
            <div className="mt-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Likely causes
              </div>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-foreground">
                {diagnosis.likely_causes.map((cause, index) => (
                  <li key={index}>{cause}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {diagnosis.suggested_fixes.length > 0 ? (
            <div className="mt-3">
              <div className="text-xs font-medium uppercase tracking-wide text-status-ok">
                Suggested fixes
              </div>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-foreground">
                {diagnosis.suggested_fixes.map((fix, index) => (
                  <li key={index}>{fix}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
