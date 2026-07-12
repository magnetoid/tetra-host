"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { faCircleCheck, faGear } from "@/lib/icons"
import type { ProjectRecord } from "@/lib/types"

const inputClass =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"

function Field({
  label,
  hint,
  value,
  onChange,
  placeholder,
  mono = true,
}: {
  label: string
  hint?: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  mono?: boolean
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`mt-1 ${inputClass} ${mono ? "font-mono" : ""}`}
      />
      {hint ? <span className="mt-1 block text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  )
}

/** Edit an app's identity + build/run settings (Coolify PATCH via the panel). */
export function EditAppForm({ app }: { app: ProjectRecord }) {
  const router = useRouter()
  const [name, setName] = useState(app.name)
  const [fqdn, setFqdn] = useState(app.fqdn || app.primary_domain || "")
  const [installCommand, setInstallCommand] = useState(app.install_command || "")
  const [buildCommand, setBuildCommand] = useState(app.build_command || "")
  const [startCommand, setStartCommand] = useState(app.start_command || "")
  const [baseDir, setBaseDir] = useState(app.base_directory || "")
  const [publishDir, setPublishDir] = useState(app.publish_directory || "")
  const [ports, setPorts] = useState(app.ports_exposes || "")

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function save(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaved(false)
    setSaving(true)
    try {
      const res = await fetch(`/api/proxy/projects/${app.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          fqdn,
          install_command: installCommand,
          build_command: buildCommand,
          start_command: startCommand,
          base_directory: baseDir,
          publish_directory: publishDir,
          ports_exposes: ports,
        }),
      })
      const payload = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(payload.detail ?? "Couldn't save app settings.")
        return
      }
      setSaved(true)
      router.refresh()
    } catch {
      setError("Network error — please retry.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save} className="space-y-5">
      {error ? <AlertBanner tone="error">{error}</AlertBanner> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="App name" value={name} onChange={setName} mono={false} placeholder="my-app" />
        <Field label="Domain" value={fqdn} onChange={setFqdn} placeholder="app.example.com" hint="Primary FQDN Coolify serves this app on." />
      </div>

      <div className="border-t border-border pt-4">
        <div className="text-sm font-semibold">Build &amp; run</div>
        <p className="text-xs text-muted-foreground">Applied on the next deploy.</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label="Install command" value={installCommand} onChange={setInstallCommand} placeholder="npm ci" />
          <Field label="Build command" value={buildCommand} onChange={setBuildCommand} placeholder="npm run build" />
          <Field label="Start command" value={startCommand} onChange={setStartCommand} placeholder="npm start" />
          <Field label="Exposed ports" value={ports} onChange={setPorts} placeholder="3000" hint="Comma-separated." />
          <Field label="Base directory" value={baseDir} onChange={setBaseDir} placeholder="/" />
          <Field label="Publish directory" value={publishDir} onChange={setPublishDir} placeholder="dist" />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" icon={faGear} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
        {saved ? (
          <span className="inline-flex items-center gap-1.5 text-sm text-status-ok">
            <FontAwesomeIcon icon={faCircleCheck} className="h-3.5 w-3.5" />
            Saved — redeploy to apply build changes.
          </span>
        ) : null}
      </div>
    </form>
  )
}
