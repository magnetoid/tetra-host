---
type: system-patterns
status: active
tags: [architecture]
---

# System Patterns

## Architecture overview
The platform is split into a Python backend for API, auth, service orchestration, and operational integrations, plus a modern frontend for the customer control panel. Domain and integration logic should stay behind explicit service boundaries rather than leaking into route handlers or UI code.

## Conventions
- Prefer typed schemas and explicit API contracts.
- Keep route handlers thin; move business logic into reusable services.
- Design for multi-tenant isolation in data access, API responses, and admin behavior.
- Favor maintainable, modern implementations over legacy-style glue code.
- Add or update tests when introducing architectural or behavioral changes.

## Patterns in use
- Thin web/API layer over testable service modules.
- Contract-first backend responses for frontend consumption.
- Incremental migration from platform-global behavior toward tenant-aware behavior.
- Torsor charter and architecture notes act as persistent engineering guardrails.
