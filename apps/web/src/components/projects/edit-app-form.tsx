"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { AlertBanner } from "@/components/ui/alert-banner"
import { Button } from "@/components/ui/button"
import { useAction } from "@/hooks/use-action"
import { apiFetch } from "@/lib/client-api"
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
  const { run, pending, error } = useAction()
  const [name, setName] = useState(app.name)
  const [fqdn, setFqdn] = useState(app.fqdn || app.primary_domain || "")
  const [installCommand, setInstallCommand] = useState(app.install_command || "")
  const [buildCommand, setBuildCommand] = useState(app.build_command || "")
  const [startCommand, setStartCommand] = useState(app.start_command || "")
  const [baseDir, setBaseDir] = useState(app.base_directory || "")
  const [publishDir, setPublishDir] = useState(app.publish_directory || "")
  const [ports, setPorts] = useState(app.ports_exposes || "")

  const [saved, setSaved] = useState(false)

  async function save(event: React.FormEvent) {
    event.preventDefault()
    setSaved(false)
    const ok = await run(
      () =>
        apiFetch(`/api/proxy/projects/${app.id}`, {
          method: "PATCH",
          body: {
            name,
            fqdn,
            install_command: installCommand,
            build_command: buildCommand,
            start_command: startCommand,
            base_directory: baseDir,
            publish_directory: publishDir,
            ports_exposes: ports,
          },
          errorMessage: "Couldn't save app settings.",
        }),
      { key: "save" },
    )
    if (ok) setSaved(true)
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
        <Button type="submit" variant="primary" icon={faGear} disabled={pending !== null}>
          {pending !== null ? "Saving…" : "Save changes"}
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
