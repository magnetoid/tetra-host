---
type: charter
status: active
tags: [charter]
---

# Project Charter

## What we are building
Tetra Host is a Cloud Industry branded multi-tenant hosting platform that gives customers a modern control panel over infrastructure and platform services such as application hosting, DNS, mail, and operational visibility. It combines a Python backend and a modern web frontend into a single product intended to feel premium, fast, and technically serious.

## Why it exists
The platform exists to provide a customer-facing hosting experience that is stronger than generic panels: clearer UX, better operational integration, stronger architecture, and a product surface that can evolve into a cutting-edge managed hosting platform.

## Non-negotiable principles
- Code quality is a product feature; implement with high-quality, cutting-edge engineering standards appropriate for a cutting-edge platform.
- Favor durable architecture over quick hacks; changes should improve maintainability, clarity, and extensibility.
- Multi-tenant correctness is mandatory; platform-global shortcuts should be treated as temporary debt, not final design.
- Prefer explicit contracts, typed boundaries, and testable service layers over implicit coupling.
- UI and backend work should feel premium: clean, modern, reliable, and production-minded.
- Markdown under `.torsor/` is project memory and architectural intent; keep it accurate as the codebase evolves.
- Build provider integrations against the latest official API docs, not memory: before adding or changing Coolify/Cloudflare/Mailcow code, consult and combine the current upstream API reference (use the `provider-api-docs` skill) and verify a capability exists upstream before building on it.
- Tetra Host is a cutting-edge, Vercel-like, open-source hosting platform; hold every part to that bar — premium UX, modern architecture, and production-grade reliability — and keep it suitable for public open-source release.
- Compose the platform from best-in-class open source: prefer integrating high-quality, well-known open-source apps/services to build the hosting infrastructure over reinventing them, and use the right language for the job (Python + TypeScript today; Go or other languages where they fit).
- Keep `tetra-cli` in step with the dashboard: when adding a dashboard feature, also implement the best, most-automatable parts in the CLI, so the whole platform is operable from the command line (Vercel-style dashboard + CLI parity).
- Near-term platform strategy: operate in symbiosis with Coolify (application hosting) and Cloudflare (DNS), and consolidate by migrating all websites onto Coolify — partly to relieve the production server's disk/space pressure, which is a real constraint to design around.
- Email runs on a Tetra-Host-compatible solution OFF the shared host: Mailcow can't coexist there (the existing Plesk/Postfix mail server already owns the mail ports), so use a dedicated mail host or a managed/API email service and build the panel integration to match — don't force self-hosted mail onto the constrained box.
