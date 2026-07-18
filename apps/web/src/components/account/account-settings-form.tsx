"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
import { faCircleCheck, faKey } from "@/lib/icons"

function fieldClass() {
  return [
    "w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground",
    "placeholder:text-muted-foreground focus:border-primary focus:outline-none",
  ].join(" ")
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-muted-foreground">{children}</label>
}

type ProfileProps = { fullName: string; email: string }

function ProfileForm({ fullName, email }: ProfileProps) {
  const { run, pending, error } = useAction()
  const [name, setName] = useState(fullName)
  const [mail, setMail] = useState(email)
  const [ok, setOk] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setOk(false)
    const saved = await run(
      () =>
        apiFetch("/api/proxy/account", {
          method: "PATCH",
          body: { full_name: name, email: mail },
          errorMessage: "Could not update the profile.",
        }),
      { key: "profile" },
    )
    if (saved) setOk(true)
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-border bg-muted/40 p-6">
      <h2 className="text-lg font-medium">Profile</h2>
      <p className="mt-1 text-sm text-muted-foreground">Update the name and email on your account.</p>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Full name</Label>
          <input
            aria-label="Full name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={fieldClass()}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Email</Label>
          <input
            aria-label="Email"
            type="email"
            required
            value={mail}
            onChange={(e) => setMail(e.target.value)}
            className={`${fieldClass()} font-mono`}
          />
        </div>
      </div>

      {ok ? (
        <p role="status" className="mt-4 rounded-lg bg-status-ok/10 px-3 py-2 text-sm text-status-ok">
          Profile updated.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 rounded-lg bg-status-err/10 px-3 py-2 text-sm text-status-err">
          {error}
        </p>
      ) : null}

      <div className="mt-4">
        <Button type="submit" variant="primary" icon={faCircleCheck} disabled={pending !== null}>
          Save profile
        </Button>
      </div>
    </form>
  )
}

function PasswordForm() {
  const { run, pending, error, setError } = useAction()
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [confirm, setConfirm] = useState("")
  const [ok, setOk] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setOk(false)
    if (next !== confirm) {
      setError("New passwords do not match.")
      return
    }
    const changed = await run(
      () =>
        apiFetch("/api/proxy/account/password", {
          method: "POST",
          body: { current_password: current, new_password: next },
          errorMessage: "Could not change the password.",
        }),
      { key: "password", refresh: false },
    )
    if (changed) {
      setOk(true)
      setCurrent("")
      setNext("")
      setConfirm("")
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-border bg-muted/40 p-6">
      <h2 className="text-lg font-medium">Change password</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Minimum 10 characters. You&apos;ll need your current password.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label>Current</Label>
          <input
            aria-label="Current password"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className={fieldClass()}
          />
        </div>
        <div className="space-y-1.5">
          <Label>New</Label>
          <input
            aria-label="New password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className={fieldClass()}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Confirm new</Label>
          <input
            aria-label="Confirm new password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={fieldClass()}
          />
        </div>
      </div>

      {ok ? (
        <p role="status" className="mt-4 rounded-lg bg-status-ok/10 px-3 py-2 text-sm text-status-ok">
          Password changed.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 rounded-lg bg-status-err/10 px-3 py-2 text-sm text-status-err">
          {error}
        </p>
      ) : null}

      <div className="mt-4">
        <Button type="submit" variant="primary" icon={faKey} disabled={pending !== null}>
          Change password
        </Button>
      </div>
    </form>
  )
}

export function AccountSettingsForm({ fullName, email }: ProfileProps) {
  return (
    <div className="space-y-6">
      <ProfileForm fullName={fullName} email={email} />
      <PasswordForm />
    </div>
  )
}
