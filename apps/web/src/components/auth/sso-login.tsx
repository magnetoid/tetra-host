"use client"

import { useState } from "react"

export function SsoLogin() {
  const [open, setOpen] = useState(false)
  const [slug, setSlug] = useState("")

  function go(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const clean = slug.trim().toLowerCase()
    if (clean) window.location.href = `/auth/sso/${encodeURIComponent(clean)}/login`
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-3 w-full rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium transition hover:border-primary/40 hover:bg-accent"
      >
        Sign in with SSO
      </button>
    )
  }

  return (
    <form onSubmit={go} className="mt-3 flex gap-2">
      <input
        aria-label="Workspace"
        autoFocus
        value={slug}
        onChange={(event) => setSlug(event.target.value)}
        placeholder="your-workspace"
        className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"
      />
      <button
        type="submit"
        className="shrink-0 rounded-xl bg-foreground px-4 py-2.5 text-sm font-medium text-background transition hover:bg-foreground/90"
      >
        Continue
      </button>
    </form>
  )
}
