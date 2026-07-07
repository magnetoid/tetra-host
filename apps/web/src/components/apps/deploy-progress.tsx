"use client"

import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Modal } from "@/components/ui/modal"
import { faArrowUpRightFromSquare, faCircleCheck, faTriangleExclamation } from "@/lib/icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

export type InstallResult = { ok: boolean; message?: string; detail?: string; domain?: string }

type Line = { text: string; done: boolean }

const STAGES = [
  "Resolving app template",
  "Pulling container images",
  "Creating containers",
  "Starting services",
  "Configuring edge routing",
  "Running health checks",
]

const SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
const TYPE_MS = 22 // per-character typing cadence
const HOLD_MS = 260 // pause after a stage finishes typing

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * Terminal-style animated deploy popup. Types out deploy stages char-by-char while
 * the (blocking) install request runs, then reconciles with the real result — a
 * green success line or the actual error. Purely cosmetic staging; the source of
 * truth is always `run()`'s resolved result.
 */
export function DeployProgress({
  open,
  appName,
  onOpenChange,
  run,
  onSuccess,
}: {
  open: boolean
  appName: string
  onOpenChange: (open: boolean) => void
  run: () => Promise<InstallResult>
  onSuccess?: () => void
}) {
  const [lines, setLines] = useState<Line[]>([])
  const [typing, setTyping] = useState("")
  const [status, setStatus] = useState<"deploying" | "success" | "error">("deploying")
  const [result, setResult] = useState<InstallResult | null>(null)
  const [frame, setFrame] = useState(0)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  // Spinner frame ticker (only while deploying).
  useEffect(() => {
    if (status !== "deploying") return
    const id = setInterval(() => setFrame((f) => (f + 1) % SPINNER.length), 90)
    return () => clearInterval(id)
  }, [status])

  // Auto-scroll the terminal as lines arrive.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [lines, typing])

  // Drive the animation + real request whenever the popup opens. State starts fresh
  // via a keyed remount (see AppMarketplace), so no reset is needed here — and the
  // driver is deferred to a microtask so no setState runs synchronously in the effect.
  useEffect(() => {
    if (!open) return
    let alive = true
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

    const finished = run() // kick off the real install immediately (runs in parallel)
    let outcome: InstallResult | null = null
    finished.then((r) => {
      outcome = r
    })

    async function type(stage: string) {
      if (prefersReduced) {
        setTyping(stage)
        return
      }
      for (let i = 1; i <= stage.length && alive; i++) {
        setTyping(stage.slice(0, i))
        await sleep(TYPE_MS)
      }
    }

    async function drive() {
      for (const stage of STAGES) {
        if (!alive) return
        if (outcome && !outcome.ok) break // real failure → stop staging early
        await type(stage)
        if (!alive) return
        setLines((prev) => [...prev, { text: stage, done: true }])
        setTyping("")
        await sleep(prefersReduced ? 0 : HOLD_MS)
      }
      // Reconcile with the real result (await it if the request is still in flight).
      const final = outcome ?? (await finished)
      if (!alive) return
      if (final.ok) {
        setResult(final)
        setStatus("success")
        onSuccess?.()
      } else {
        setLines((prev) => [...prev, { text: final.detail ?? "Deploy failed.", done: false }])
        setResult(final)
        setStatus("error")
      }
    }

    // Defer so no setState runs during the effect's synchronous phase.
    queueMicrotask(() => {
      if (alive) void drive()
    })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const deploying = status === "deploying"

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        // Don't let the user dismiss mid-deploy (the request keeps running).
        if (deploying) return
        onOpenChange(next)
      }}
      title={
        status === "success"
          ? `${appName} deployed`
          : status === "error"
            ? `${appName} — deploy failed`
            : `Deploying ${appName}`
      }
      description={
        deploying ? "Provisioning your app — this can take a moment." : undefined
      }
      className="max-w-xl"
      footer={
        deploying ? undefined : (
          <>
            {status === "success" && result?.domain ? (
              <a
                href={`https://${result.domain}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
              >
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="h-3.5 w-3.5" />
                Open app
              </a>
            ) : null}
            <Button variant={status === "success" ? "primary" : "secondary"} onClick={() => onOpenChange(false)}>
              {status === "success" ? "Done" : "Close"}
            </Button>
          </>
        )
      }
    >
      <div
        ref={scrollRef}
        className="max-h-72 overflow-y-auto rounded-xl border border-border bg-black/70 p-4 font-mono text-xs leading-relaxed text-zinc-300"
        aria-live="polite"
      >
        {lines.map((line, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className={line.done ? "text-status-ok" : "text-status-err"}>
              {line.done ? "✓" : "✗"}
            </span>
            <span className={line.done ? "" : "text-status-err"}>{line.text}</span>
          </div>
        ))}

        {typing ? (
          <div className="flex items-start gap-2">
            <span className="text-accent-cyan">{SPINNER[frame]}</span>
            <span>
              {typing}
              <span className="ml-0.5 inline-block w-1.5 animate-pulse bg-zinc-400">&nbsp;</span>
            </span>
          </div>
        ) : null}

        {status === "success" ? (
          <div className="mt-2 flex items-center gap-2 text-status-ok">
            <FontAwesomeIcon icon={faCircleCheck} className="h-3.5 w-3.5" />
            <span>{result?.message ?? `${appName} is live.`}</span>
          </div>
        ) : null}
        {status === "error" ? (
          <div className="mt-2 flex items-center gap-2 text-status-err">
            <FontAwesomeIcon icon={faTriangleExclamation} className="h-3.5 w-3.5" />
            <span>Deployment did not complete.</span>
          </div>
        ) : null}
      </div>
    </Modal>
  )
}
