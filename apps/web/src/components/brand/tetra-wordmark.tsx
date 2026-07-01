/**
 * Tetra AI Cloud wordmark lockup — the tetrahedron glyph + product name.
 * Server-safe (pure SVG + text). Size the glyph via `className` on the wrapper.
 */
export function TetraWordmark({ label = "Tetra AI Cloud" }: { label?: string }) {
  return (
    <span className="flex items-center gap-3">
      <span className="grid h-9 w-9 place-items-center rounded-lg border border-primary/40 bg-primary/10">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M12 2 L22 20 L2 20 Z"
            stroke="#a78bfa"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M12 2 L12 20 M12 2 L2 20 M12 2 L22 20"
            stroke="#22d3ee"
            strokeWidth="1"
            opacity="0.55"
          />
        </svg>
      </span>
      <span className="font-[family-name:var(--font-space-grotesk)] text-lg font-semibold tracking-tight">
        {label}
      </span>
    </span>
  )
}
