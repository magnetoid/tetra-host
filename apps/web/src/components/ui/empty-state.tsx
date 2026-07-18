export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  /** Optional primary next-action (button/link) — turns a dead-end into a path forward. */
  action?: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted p-8 text-sm text-muted-foreground">
      <div className="font-medium text-foreground">{title}</div>
      {description ? <p className="mt-2 max-w-2xl">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
