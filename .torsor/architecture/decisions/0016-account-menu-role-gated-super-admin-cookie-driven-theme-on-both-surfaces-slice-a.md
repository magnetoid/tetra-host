---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-04T02:08:45'
updated: '2026-07-04T02:08:45'
rules:
- id: tetra-role-exposed-and-gated
  rule: 'The signed-in admin''s role must be available to templates/UI (panel: session
    + request.state.current_admin_role set authoritatively from the DB in get_current_admin;
    console: admin.role from /auth/me), and every platform-admin-only surface must
    be gated on it in BOTH the account dropdown and the sidebar nav (PluginMeta.platform_admin_only);
    never show or link a platform-admin surface to a non-platform admin.'
- id: tetra-theme-cookie-ssr-no-flash
  rule: "Theme is a cookie-persisted preference resolved server-side before first\
    \ paint (panel: no-flash <head> script sets <html>.dark; console: data-theme on\
    \ <html> read from the cookie in the root layout), with semantic colors as CSS\
    \ variables that flip light/dark. Light mode must remap the fixed utility set\
    \ the templates use \u2014 shipping a theme toggle that leaves contrast broken\
    \ is not acceptable."
- id: tetra-account-menu-parity
  rule: "Both surfaces expose the same upper-right account dropdown (profile header,\
    \ Account, Super Admin [platform-admin only], theme toggle, logout), reached from\
    \ the header \u2014 not the sidebar; the Account page is its own module/route\
    \ (app/modules/account, console /account), never bolted onto another module."
---

# ADR 0016: Account menu + role-gated Super Admin + cookie-driven theme, on both surfaces (Slice A)

## Context
Both surfaces (FastAPI/Jinja panel in app/, Next.js console in apps/web/) rendered a bare upper-right header (static name/email + a logout form), had no account/profile page, and the panel never exposed the signed-in admin's role to templates — so it could not gate a Super Admin link and even leaked a "Platform controls" link to non-admin owners. User asked for a tenant/profile/settings dropdown containing a Super Admin page, plus a light/dark theme toggle, on both surfaces. First of a multi-slice program (account menu → account settings/change-password → audit viewer → status page → command palette → tenant impersonation).

## Decision
Added an upper-right ACCOUNT DROPDOWN to both surfaces: panel uses a dependency-free <details>/<summary> menu in base.html; console uses a hand-rolled headless "use client" UserMenu (no Radix dep) with outside-click + Escape (restoring focus to the trigger). Both show a profile header, an Account link, a Super Admin link gated to platform admins, a theme toggle, and logout (CSRF-preserving on the panel). Role is now first-class: stored in the panel session at login and mirrored to request.state.current_admin_role in inject_core_context, with get_current_admin setting it authoritatively from the DB on protected routes; PluginMeta gained platform_admin_only (admin plugin flagged) and the sidebar nav is filtered in-template by the DB-sourced role. New self-contained account module (app/modules/account, empty nav_href) + console /account page give a read-only profile (change-password/notifications deferred to the next slice). THEME is a cookie-persisted preference resolved server-side before first paint (panel: no-flash <head> script toggling <html>.dark; console: data-theme on <html> from the cookie in the async root layout), with semantic tokens as CSS variables that flip light/dark; light mode comprehensively remaps the fixed Tailwind zinc/white/black/colored utilities the templates use so there is no contrast breakage. Verified: backend + ruff green, console pnpm check (76 vitest incl. 6 UserMenu), plus a live Playwright pass logging into the panel and confirming both themes render legibly and the role-gated dropdown works. Adversarially reviewed (4 dimensions, 20 agents); 8 confirmed findings fixed — chiefly an incomplete light-mode remap on both surfaces, and a dropdown focus-return a11y gap.

## Consequences
Platform-admin surfaces are consistently gated by the DB-sourced role on both the dropdown and the sidebar; the owner "Platform controls" leak is closed. Existing panel sessions created before this deploy briefly lack the session role, but get_current_admin repopulates it from the DB on every protected page, so the dropdown/nav stay correct and self-heal on next login. The theme system is now the platform pattern; any new component must use semantic tokens (or be covered by the light-mode remap) to avoid contrast regressions — light mode via utility-class overrides is inherently a tail to maintain as new colored utilities appear. Account page is intentionally read-only until the account-settings slice (change-password + notification preferences). CLI parity: `tetra whoami` already surfaces the profile; a `tetra account passwd` verb lands with the change-password slice.
