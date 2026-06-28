"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { safeNextPath } from "@/lib/utils"

export function LoginForm({ nextPath }: { nextPath?: string }) {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          next: safeNextPath(nextPath),
        }),
      })

      if (!response.ok) {
        const payload = (await response.json()) as { error?: string }
        setError(payload.error ?? "Unable to sign in.")
        return
      }

      const payload = (await response.json()) as { next?: string }
      router.push(payload.next ?? "/dashboard")
      router.refresh()
    } catch {
      setError("Unable to reach the authentication service.")
    } finally {
      setPending(false)
    }
  }

  return (
    <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      <label className="block text-sm">
        <span className="mb-2 block text-zinc-300">Email</span>
        <input
          name="email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="admin@company.com"
          className="w-full rounded-xl border border-border bg-background px-3 py-2.5 outline-none focus:border-zinc-500"
        />
      </label>
      <label className="block text-sm">
        <span className="mb-2 block text-zinc-300">Password</span>
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Password"
          className="w-full rounded-xl border border-border bg-background px-3 py-2.5 outline-none focus:border-zinc-500"
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-xl bg-primary px-4 py-2.5 font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending ? "Signing in..." : "Access dashboard"}
      </button>
    </form>
  )
}
