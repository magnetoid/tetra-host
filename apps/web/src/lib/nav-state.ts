"use client"

import { useCallback, useSyncExternalStore } from "react"

/**
 * Which sidebar groups are open, remembered per browser. Kept in localStorage
 * (a per-viewer convenience); every access is guarded because storage can be
 * missing or throw (private windows, blocked site data). The server render and
 * the first client render use the default, so hydration always matches.
 */
const STORAGE_KEY = "tetra.nav.open"
const EVENT = "tetra-nav-open"

function read(): Record<string, boolean> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(EVENT, onChange)
  window.addEventListener("storage", onChange)
  return () => {
    window.removeEventListener(EVENT, onChange)
    window.removeEventListener("storage", onChange)
  }
}

// Snapshots must be stable between changes, so cache the raw string's parse.
let cachedRaw: string | null | undefined
let cachedState: Record<string, boolean> = {}

function snapshot(): Record<string, boolean> {
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    raw = null
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw
    cachedState = read()
  }
  return cachedState
}

const EMPTY: Record<string, boolean> = {}

export function setNavOpen(key: string, open: boolean): void {
  // From the first toggle on, collapsibles animate (see globals.css).
  document.documentElement.dataset.navAnimate = ""
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...read(), [key]: open }))
  } catch {
    // Storage unavailable: the toggle still works for this page view via the event.
  }
  window.dispatchEvent(new Event(EVENT))
}

/** `[open, toggle]` for a sidebar group; `fallback` applies until the user toggles it. */
export function useNavOpen(key: string, fallback: boolean): [boolean, () => void] {
  const state = useSyncExternalStore(subscribe, snapshot, () => EMPTY)
  const open = state[key] ?? fallback
  const toggle = useCallback(() => setNavOpen(key, !open), [key, open])
  return [open, toggle]
}
