---
type: active-context
status: active
tags:
- active
links: []
created: '2026-07-01T02:43:33'
updated: '2026-07-01T02:43:33'
---

# Active Context

## Current focus
Elevating the console/panel to a premium Tetra Host brand and firming up the platform's mail story. Just shipped the redesigned FastAPI login (Tetra tetrahedron identity) to production; now evaluating which best-in-class OSS mail server the multi-tenant platform standardizes on (every tenant provisions mail against it).

## Open questions
MAIL SERVER (undecided — needs user ratification before an ADR): platform-standard OSS mail server for multi-tenant provisioning. Candidates: Mailcow (already the integrated provider in app/services/mailcow.py + CLAUDE.md; richest admin API + Docker-native, fits the Tetra Engine docker-compose model; strong DKIM/SPF/DMARC automation synergy with the platform's existing Cloudflare DNS control; but heavy ~4-6GB RAM and disk on the shared, ~84%-full box) vs Stalwart (modern Rust, low footprint, JMAP+IMAP+SMTP, multi-tenant, but would need a new provider client) vs Mailu (lighter Docker middle-ground). Recommendation on record: keep Mailcow unless RAM/disk is the binding constraint, in which case evaluate Stalwart. Sub-question: check the box's free RAM/disk to make the call concrete. Also: Mailcow API token is still EMPTY in prod /opt/tetra-host/.env — provisioning flow not yet wired.
