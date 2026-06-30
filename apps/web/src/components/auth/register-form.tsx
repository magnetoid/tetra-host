"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"

export function RegisterForm() {
  const router = useRouter()
  const [orgName, setOrgName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          org_name: orgName,
          email,
          password,
        }),
      })

      if (!response.ok) {
        const payload = (await response.json()) as { error?: string }
        setError(payload.error ?? "Registration failed.")
        return
      }

      router.push("/dashboard")
      router.refresh()
    } catch {
      setError("Unable to reach the registration service.")
    } finally {
      setPending(false)
    }
  }

  return (
    <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      <label className="block text-sm">
        <span className="mb-2 block text-zinc-300">Organisation name</span>
        <input
          aria-label="Organisation name"
          name="org_name"
          type="text"
          autoComplete="organization"
          required
          value={orgName}
          onChange={(event) => setOrgName(event.target.value)}
          placeholder="Acme Corp"
          className="w-full rounded-xl border border-border bg-background px-3 py-2.5 outline-none focus:border-zinc-500"
        />
      </label>
      <label className="block text-sm">
        <span className="mb-2 block text-zinc-300">Work email</span>
        <input
          aria-label="Email"
          name="email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-xl border border-border bg-background px-3 py-2.5 outline-none focus:border-zinc-500"
        />
      </label>
      <label className="block text-sm">
        <span className="mb-2 block text-zinc-300">Password</span>
        <input
          aria-label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="At least 10 characters"
          className="w-full rounded-xl border border-border bg-background px-3 py-2.5 outline-none focus:border-zinc-500"
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-xl bg-primary px-4 py-2.5 font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending ? "Creating account..." : "Create account"}
      </button>
    </form>
  )
}
