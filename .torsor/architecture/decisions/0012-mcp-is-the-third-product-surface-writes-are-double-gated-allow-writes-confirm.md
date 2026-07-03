---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-03T02:24:25'
updated: '2026-07-03T02:24:25'
rules:
- id: tetra-mcp-writes-double-gated
  rule: MCP write tools must require both the --allow-writes server flag and a per-call
    confirm=true argument; never expose billable/platform-admin operations (infra
    provisioning, plans, tenants) or DNS writes over MCP.
- id: tetra-mcp-parity-via-api
  rule: "MCP tools must be thin wrappers over TetraClient//api/v1 (same contract as\
    \ dashboard and CLI) \u2014 no MCP-only backend endpoints or privileged side channels."
---

# ADR 0012: MCP is the third product surface; writes are double-gated (—allow-writes + confirm)

## Context
Phase 4 of the ratified Tetra AI Cloud program (ADR 0004) calls for an AI/MCP control plane as a fast-follow once the Phase-1 Vercel loop shipped. MCP is Linux-Foundation-governed (donated Dec 2025) and safe to standardize on. The charter's parity rule already requires dashboard ↔ CLI parity; an AI agent should see exactly the same contract. The CLI has a hard no-new-dependencies rule (argparse + httpx only), and MCP's stdio transport is just newline-delimited JSON-RPC 2.0 — implementable with the stdlib. Research (Cloudflare Code Mode) favors few, typed tools over one tool per endpoint.

## Decision
The platform exposes a first-party MCP server via `tetra mcp serve` (tetra_cli/mcp.py): a hand-rolled stdio JSON-RPC server, no SDK dependency, whose tools are thin typed wrappers over TetraClient and the same /api/v1 contract as the dashboard and CLI — making MCP the third parity surface. The tool set is curated and small (8 reads, 4 writes), not auto-generated from OpenAPI. Safety model: reads are always available; write tools (a) only exist when the operator starts the server with --allow-writes and (b) each call must also pass confirm=true — two explicit human decisions before anything changes. Billable/platform-admin operations (Hetzner provisioning, plans, tenants) and DNS writes are deliberately not exposed over MCP at all.

## Consequences
Any MCP client (Claude Code/Desktop, etc.) can operate a tenant's apps — list, inspect failed builds via get_deployment's full log, deploy, roll back — with the panel's existing token auth and tenant scoping enforced server-side by /api/v1. New dashboard features should extend the parity rule to three surfaces where it makes sense (dashboard + CLI + MCP tool). The MCP surface must stay curated: adding a tool is a product decision, and write tools must keep the double gate. Protocol maintenance is on us (no SDK), but the surface area is tiny (initialize/ping/tools.list/tools.call).
