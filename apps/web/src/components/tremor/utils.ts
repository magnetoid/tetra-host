// Vendored Tremor Raw utilities (github.com/tremorlabs/tremor, MIT license).
// Adopted directly (Tailwind-v4 / React-19 / Recharts-3 native) instead of the
// @tremor/react npm package, which requires React 18 + Recharts 2 + Tailwind-v3 config.
import clsx, { type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

// Tremor cx [v0.0.0]
export function cx(...args: ClassValue[]) {
  return twMerge(clsx(...args))
}

// Tremor focusRing [v0.0.1] — themed to the Tetra brand (violet) rather than blue.
export const focusRing = [
  "outline outline-offset-2 outline-0 focus-visible:outline-2",
  "outline-primary",
]
