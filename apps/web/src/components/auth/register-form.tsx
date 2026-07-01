"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"

const INPUT_CLASS =
  "w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

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
    <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}
      <label className="block text-sm">
        <span className="mb-2 block font-medium text-zinc-300">Organisation name</span>
        <input
          aria-label="Organisation name"
          name="org_name"
          type="text"
          autoComplete="organization"
          required
          value={orgName}
          onChange={(event) => setOrgName(event.target.value)}
          placeholder="Acme Corp"
          className={INPUT_CLASS}
        />
      </label>
      <label className="block text-sm">
        <span className="mb-2 block font-medium text-zinc-300">Work email</span>
        <input
          aria-label="Email"
          name="email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@company.com"
          className={INPUT_CLASS}
        />
      </label>
      <label className="block text-sm">
        <span className="mb-2 block font-medium text-zinc-300">Password</span>
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
          className={INPUT_CLASS}
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary to-indigo-600 px-4 py-3 font-medium text-white shadow-lg shadow-primary/25 transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 focus:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending ? "Creating account..." : "Create account"}
      </button>
    </form>
  )
}
