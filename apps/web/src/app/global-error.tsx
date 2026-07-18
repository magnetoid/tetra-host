"use client"

/**
 * Last-resort boundary — replaces the root layout when even it fails, so it must
 * own <html>/<body> and stay dependency-free (inline styles; globals.css may not
 * have loaded). Kept deliberately minimal.
 */
export default function GlobalError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#070709",
          color: "#f4f4f6",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div role="alert" style={{ textAlign: "center", maxWidth: 420, padding: 24 }}>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>
            Tetra AI Cloud hit an unexpected error
          </h1>
          <p style={{ color: "#a1a1aa", fontSize: 14, lineHeight: 1.6, marginTop: 12 }}>
            The console failed to render. Try again — if the problem persists, the control plane
            itself may be restarting.
          </p>
          {error.digest ? (
            <p style={{ fontFamily: "monospace", fontSize: 12, color: "#71717a" }}>
              ref {error.digest}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => unstable_retry()}
            style={{
              marginTop: 16,
              padding: "8px 16px",
              borderRadius: 6,
              border: "none",
              background: "#7c3aed",
              color: "#fafafa",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  )
}
