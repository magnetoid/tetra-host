"use client"

import { Toaster as SonnerToaster } from "sonner"

/** App-wide toast outlet (sonner), themed to match the console tokens. */
export function Toaster({ theme }: { theme: "light" | "dark" }) {
  return (
    <SonnerToaster
      theme={theme}
      position="bottom-right"
      closeButton
      toastOptions={{
        style: {
          background: "var(--card)",
          color: "var(--card-foreground)",
          border: "1px solid var(--border)",
        },
      }}
    />
  )
}
