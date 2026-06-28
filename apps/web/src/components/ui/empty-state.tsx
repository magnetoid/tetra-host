export function EmptyState({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-muted p-8 text-sm text-zinc-400">
      <div className="font-medium text-zinc-300">{title}</div>
      {description ? <p className="mt-2">{description}</p> : null}
    </div>
  )
}
