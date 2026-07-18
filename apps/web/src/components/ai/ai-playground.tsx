"use client"

import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { apiFetch } from "@/lib/client-api"
import { faWandSparkles } from "@/lib/icons"
import type { AiModel, AiStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

type ChatMessage = { role: "user" | "assistant"; content: string }

const TEXTAREA =
  "w-full resize-none rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

function pickDefaultModel(models: AiModel[]): string {
  const preferred = models.find((m) => /gpt-4o-mini|haiku|llama-3\.\d-8b/i.test(m.id))
  return preferred?.id ?? models[0]?.id ?? ""
}

export function AiPlayground({
  models,
  status,
  initialBalanceUsd,
}: {
  models: AiModel[]
  status: AiStatus
  initialBalanceUsd: number
}) {
  const [model, setModel] = useState(() => pickDefaultModel(models))
  const [prompt, setPrompt] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [balance, setBalance] = useState(initialBalanceUsd)
  const [lastCost, setLastCost] = useState<number | null>(null)

  async function send(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = prompt.trim()
    if (!content || !model) return
    const next: ChatMessage[] = [...messages, { role: "user", content }]
    setMessages(next)
    setPrompt("")
    setPending(true)
    setError(null)
    try {
      const payload = await apiFetch<{
        completion?: { choices?: { message?: { content?: string } }[] }
        usage?: { billed_usd?: number }
        balance_usd?: number
      }>("/api/proxy/ai/chat", {
        method: "POST",
        body: { model, messages: next },
        errorMessage: "Request failed.",
      })
      const reply = payload.completion?.choices?.[0]?.message?.content ?? "(no content)"
      setMessages((m) => [...m, { role: "assistant", content: reply }])
      if (typeof payload.balance_usd === "number") setBalance(payload.balance_usd)
      if (typeof payload.usage?.billed_usd === "number") setLastCost(payload.usage.billed_usd)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.")
    } finally {
      setPending(false)
    }
  }

  if (status.mode === "keys") {
    return (
      <AlertBanner tone="info">
        This platform provisions per-tenant AI keys — use your provisioned key to call OpenRouter
        directly. The in-console playground runs on the shared-gateway billing mode.
      </AlertBanner>
    )
  }

  if (!status.configured || status.mode === "disabled") {
    return (
      <AlertBanner tone="info">
        AI isn&apos;t configured on this platform yet. A platform admin connects OpenRouter to enable
        the gateway.
      </AlertBanner>
    )
  }

  const noCredit = balance <= 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Model</span>
          <input
            aria-label="Model"
            list="ai-models"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-72 rounded-lg border border-border bg-background px-2.5 py-1.5 font-mono text-xs outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"
          />
          <datalist id="ai-models">
            {models.slice(0, 400).map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </datalist>
        </label>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {lastCost !== null ? <span>last: ${lastCost.toFixed(5)}</span> : null}
          <span className={cn("font-mono", noCredit ? "text-status-err" : "text-status-ok")}>
            balance ${balance.toFixed(4)}
          </span>
        </div>
      </div>

      {noCredit ? (
        <AlertBanner tone="info">
          You have no AI credit. Ask a platform admin to top up your balance to run the gateway.
        </AlertBanner>
      ) : null}
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      {messages.length > 0 ? (
        <div className="max-h-[28rem] space-y-3 overflow-y-auto rounded-lg border border-border bg-muted p-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "rounded-xl px-3 py-2 text-sm",
                m.role === "user"
                  ? "ml-8 border border-border bg-background"
                  : "mr-8 border border-primary/30 bg-primary/5",
              )}
            >
              <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                {m.role}
              </div>
              <div className="whitespace-pre-wrap">{m.content}</div>
            </div>
          ))}
          {pending ? <div className="mr-8 animate-pulse text-sm text-muted-foreground">…thinking</div> : null}
        </div>
      ) : null}

      <form onSubmit={send} className="space-y-2">
        <textarea
          aria-label="Prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              e.currentTarget.form?.requestSubmit()
            }
          }}
          rows={3}
          placeholder="Ask anything…  (⌘/Ctrl + Enter to send)"
          className={TEXTAREA}
        />
        <div className="flex justify-end">
          <Button type="submit" icon={faWandSparkles} disabled={pending || noCredit || !prompt.trim()}>
            {pending ? "…" : "Send"}
          </Button>
        </div>
      </form>
    </div>
  )
}
