---
type: progress
status: active
tags:
- active
links: []
created: '2026-07-01T02:43:33'
updated: '2026-07-01T02:43:33'
---

# Progress

DONE: Redesigned app/templates/auth/login.html — split "control plane" layout, canvas-rendered rotating wireframe tetrahedron (four provider planes as geometry), Space Grotesk/Inter/JetBrains Mono type, violet+cyan palette on a blueprint grid, SVG password reveal, a11y + reduced-motion. Committed c7c35c0, pushed to origin/main, deployed to /opt/tetra-host (fast-forward + preflight pass + systemctl restart tetra-host); verified /health ok and https://panel.cloud-industry.com/auth/login -> HTTP 200. Recorded ADR for the Tetra visual identity (mark + type + palette + quality floor) with drift rules.
IN PROGRESS: mail-server selection for the platform.
NOT DONE: Next.js console login (apps/web/src/app/auth/login) still on old styling — pending migration to the new identity.
