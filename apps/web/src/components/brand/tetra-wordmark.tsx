/**
 * Tetra wordmark — a monochrome tetrahedron glyph + product name. Inherits the
 * text colour so it reads in both themes. `compact` renders the glyph only
 * (collapsed sidebar). Server-safe (pure SVG + text).
 */
export function TetraWordmark({
  label = "Tetra AI Cloud",
  compact = false,
}: {
  label?: string
  compact?: boolean
}) {
  return (
    <span className="flex items-center gap-2.5">
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
        aria-hidden="true"
        className="shrink-0"
      >
        <path d="M12 3 3 19h18L12 3zM12 3v16M3 19l9-5 9 5" />
      </svg>
      {compact ? <span className="sr-only">{label}</span> : (
        <span className="text-sm font-semibold tracking-tight">{label}</span>
      )}
    </span>
  )
}
