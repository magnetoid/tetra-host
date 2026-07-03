"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { faWandSparkles } from "@/lib/icons"
import type { BuildDiagnosis } from "@/lib/types"

const CONFIDENCE_TONE: Record<string, string> = {
  high: "text-emerald-400",
  medium: "text-amber-400",
  low: "text-zinc-500",
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

      {error ? <p className="mt-2 text-sm text-red-400">{error}</p> : null}

      {diagnosis ? (
        <div className="mt-3 w-full rounded-2xl border border-violet-900/60 bg-violet-950/30 p-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium text-violet-200">{diagnosis.summary}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
            <span>
              category <span className="font-mono text-zinc-400">{diagnosis.category}</span>
            </span>
            <span>
              confidence{" "}
              <span className={CONFIDENCE_TONE[diagnosis.confidence] ?? "text-zinc-400"}>
                {diagnosis.confidence}
              </span>
            </span>
            <span>
              via {diagnosis.source === "ai" ? "Claude" : "heuristics"}
            </span>
          </div>

          {diagnosis.likely_causes.length > 0 ? (
            <div className="mt-3">
              <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Likely causes
              </div>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-zinc-300">
                {diagnosis.likely_causes.map((cause, index) => (
                  <li key={index}>{cause}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {diagnosis.suggested_fixes.length > 0 ? (
            <div className="mt-3">
              <div className="text-xs font-medium uppercase tracking-wide text-emerald-500">
                Suggested fixes
              </div>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-zinc-300">
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
