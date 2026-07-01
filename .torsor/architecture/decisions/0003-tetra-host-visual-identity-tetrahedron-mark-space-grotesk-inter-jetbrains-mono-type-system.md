---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-01T02:43:22'
updated: '2026-07-01T02:43:22'
rules:
- id: tetra-brand-no-emoji-icons
  description: Tetra-branded UI surfaces use inline SVG icons, not emoji glyphs, for
    UI iconography.
  severity: warn
- id: tetra-brand-type-system
  description: Branded surfaces use Space Grotesk (display), Inter (body), JetBrains
    Mono (utility/mono) rather than ad-hoc font choices.
  severity: info
- id: tetra-brand-reduced-motion
  description: Any decorative animation (e.g. the tetrahedron canvas) must honor prefers-reduced-motion.
  severity: warn
---

# ADR 0003: Tetra Host visual identity: tetrahedron mark + Space Grotesk / Inter / JetBrains Mono type system

## Context
The console login (app/templates/auth/login.html) was the first surface deliberately branded for "Tetra Host" (Cloud Industry's PaaS). The prior page was a generic dark purple-blob template with emoji icons and no distinct identity — off-bar for a premium, Vercel-like platform. We needed a durable brand system so future auth/marketing/console surfaces stay coherent instead of each reinventing a look. The name "Tetra" (tetrahedron: 4 vertices, 6 edges) also maps to the four provider planes the platform orchestrates (Coolify apps, Mailcow mail, Cloudflare DNS, edge), giving the mark real meaning.

## Decision
Adopt a Tetra Host visual identity, first shipped on the FastAPI Jinja login: (1) SIGNATURE MARK — a wireframe tetrahedron (violet->cyan glowing edges), used as an inline-SVG glyph in the wordmark lockup and, where a hero exists, as a canvas-rendered rotating object; its four vertices represent the four provider planes. (2) TYPE SYSTEM — Space Grotesk for display/headings, Inter for body, JetBrains Mono for utility/meta/status/data readouts. (3) PALETTE — deep cool near-black #070709 base, surface #0c0c12, hairline border #1c1c26, brand violet #7c3aed kept for continuity, electric cyan #22d3ee as the geometric/network accent, emerald for live status only; violet->cyan gradient reserved for the signature and primary CTA. (4) QUALITY FLOOR — real SVG icons (no emoji), visible keyboard focus rings, ARIA on interactive/error elements, and prefers-reduced-motion honored for all animation. Applies to Tetra-branded surfaces on BOTH the FastAPI panel (Tailwind CDN) and, going forward, the Next.js console — this complements, does not supersede, ADR 0002 (console component styling via shadcn/ui + Tremor), which governs component library choice rather than brand identity.

## Consequences
Positive: a coherent, ownable identity that reads as a serious modern PaaS; the mark carries product meaning (four planes). Trade-offs: the FastAPI login pulls Space Grotesk/Inter/JetBrains Mono from Google Fonts and Tailwind from CDN (consistent with existing base.html approach, but a self-hosted-assets pass is future hardening for offline/perf/privacy). The Next.js console login still uses the old styling and must be migrated to this identity to be consistent. Emoji-based iconography elsewhere in the panel is now off-brand and should be replaced incrementally.
