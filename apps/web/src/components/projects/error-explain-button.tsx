"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Modal } from "@/components/ui/modal"
import { faWandSparkles } from "@/lib/icons"
import type { ErrorDiagnosis } from "@/lib/types"

const CONFIDENCE_TONE: Record<string, string> = {
  high: "text-status-ok",
  medium: "text-status-warn",
  low: "text-muted-foreground",
}

/**
 * "Explain" affordance for one captured runtime error: fetches an AI/heuristic
 * diagnosis (`tetra ai explain-error` parity) and shows it in a modal. Mirrors
 * the deploys ExplainButton; a modal keeps the dense issues table uncluttered.
 */
export function ErrorExplainButton({ app, issueId, title }: { app: string; issueId: string; title: string }) {
  const [open, setOpen] = useState(false)
  const [diagnosis, setDiagnosis] = useState<ErrorDiagnosis | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function explain() {
    setOpen(true)
    setPending(true)
    setError(null)
    setDiagnosis(null)
    try {
      const response = await fetch(
        `/api/proxy/projects/${app}/errors/${issueId}/explain`,
      )
      const payload = (await response.json().catch(() => ({}))) as ErrorDiagnosis & {
        detail?: string
      }
      if (!response.ok) {
        setError(payload.detail ?? "Could not diagnose this error.")
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
    <>
      <Button size="sm" variant="ghost" icon={faWandSparkles} disabled={pending} onClick={explain}>
        {pending ? "Diagnosing…" : "Explain"}
      </Button>

      <Modal open={open} onOpenChange={setOpen} title="Error diagnosis" description={title}>
        {pending ? (
          <p className="text-sm text-muted-foreground">Diagnosing…</p>
        ) : error ? (
          <p className="text-sm text-status-err">{error}</p>
        ) : diagnosis ? (
          <div className="text-sm">
            <p className="font-medium text-foreground">{diagnosis.summary}</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>
                category <span className="font-mono">{diagnosis.category}</span>
              </span>
              <span>
                confidence{" "}
                <span className={CONFIDENCE_TONE[diagnosis.confidence] ?? "text-muted-foreground"}>
                  {diagnosis.confidence}
                </span>
              </span>
              <span>via {diagnosis.source === "ai" ? "Claude" : "heuristics"}</span>
            </div>

            {diagnosis.likely_causes.length > 0 ? (
              <div className="mt-4">
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
              <div className="mt-4">
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
      </Modal>
    </>
  )
}
