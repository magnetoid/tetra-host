# Reseller billing & markup model (design proposal)

Status: **proposed** · 2026-07-08 · supersedes nothing · feeds a future ADR once ratified.

## Goal
One **provider-agnostic** model for reselling third-party services to tenants at a markup —
covering today's providers (Cloudflare plans/services, OpenRouter AI usage) and the next ones
(**Hetzner** servers/traffic, …) without a per-provider billing rewrite. It must produce accurate
charges, a margin the platform controls, an auditable ledger, and hard spend ceilings.

## The two cost shapes (everything reduces to these)
| Shape | Examples | How the provider charges Tetra | How Tetra bills the tenant |
|---|---|---|---|
| **Recurring (flat)** | Cloudflare Pro/Business plan, Hetzner server monthly | fixed amount per period | subscription line item on the monthly invoice (prorated on mid-cycle change) |
| **Metered (usage)** | OpenRouter tokens, Hetzner traffic/hourly overage | per unit consumed | drawn from a **prepaid credit wallet**; provider's own cap is the hard ceiling |

## Pricing: cost → markup → resale price
Every resellable **offering** (a catalog entry keyed like `cf.plan_pro`, `ai.usage`, `hetzner.cx32`)
carries a **wholesale cost** (what Tetra pays) and a **pricing rule**:
- `markup_percent` — resale = cost × (1 + p). **Default**, e.g. p = 0.30.
- `fixed_margin` — resale = cost + $m.
- `fixed_price` — resale = absolute (ignores cost).

Resolution order: per-offering rule → per-plan override → **platform default markup** (a setting).
Platform-admin sets these; tenants only ever see the resale price.

## Metered = prepaid credits (the safe default)
For usage-based offerings the tenant **pre-buys Tetra credits** (already marked up). Credits map to a
provider spend cap: `provider_cap = tenant_credit_balance ÷ (1 + markup)`. The provider enforces the
ceiling natively — this is exactly what the OpenRouter per-tenant key `limit` already does (and why
that integration shipped first). When credits deplete, the key auto-disables; Tetra reconciles real
usage into the ledger and draws down the wallet. No runaway bills, no trust required.

## Data model (new, small, additive)
- **`PricingRule`** (config or table): `offering_key`, `provider`, `cost_shape` (recurring|metered),
  `wholesale_cost_cents` (or per-unit), `rule` (markup_percent|fixed_margin|fixed_price), `value`.
- **`TenantSubscription`** (recurring): `tenant_id`, `offering_key`, `provider`, `resale_price_cents`,
  `period_start/end`, `status`, `external_ref` (CF subscription id / Hetzner server id).
- **`TenantCredit`** (wallet, metered): `tenant_id`, `balance_cents`.
- **`CreditTransaction`**: `tenant_id`, `delta_cents`, `kind` (topup|usage|adjustment), `ref`.
- **`ResellerCharge`** (append-only **ledger** — the source of truth): `tenant_id`, `offering_key`,
  `period`, `wholesale_cost_cents`, `resale_price_cents`, `margin_cents`, `status`
  (pending|invoiced|paid). Powers invoicing **and** margin/revenue reporting.

This slots beside the existing `plans` module (a `Plan` can bundle included allowances, e.g. "$10/mo
AI credits"; overages flow through the wallet/ledger). Follows `tetra-clean-simple-core`: a new
`billing` module, thin services, not bolted onto reseller.

## Guardrails (already partly in place)
- **Kill-switch**: `reseller_cloudflare_billing_enabled` (shipped, default off) — no real charge until
  this model is live. Every provider gets the same per-provider switch.
- **Hard caps**: provider-native (OpenRouter key limit); wallet balance can't go negative.
- **Fail-closed ownership** + the **ledger** for full auditability (ties into the audit log).

## Rollout slices (each independently shippable)
1. **Pricing + ledger, no real money** — `PricingRule` + `ResellerCharge` + a "price preview" endpoint
   (resolve resale price for any offering/tenant) + admin/CLI to set markup. Safe: pure math + records.
2. **AI credit wallet** — `TenantCredit`/`CreditTransaction`; top-up ↔ OpenRouter cap; usage reconcile.
   Highest value, safest (prepaid + capped). Needs a real **provisioning** OpenRouter key.
3. **Recurring subscriptions → invoice preview** — `TenantSubscription` + monthly invoice assembly.
   Flip the Cloudflare (then Hetzner) kill-switch on once this + a plan mapping exist.
4. **Payment capture (Stripe or similar)** — separate slice; slices 1–3 are payment-rail-agnostic.

## Decisions needed before building slice 1
1. **Default markup**: percentage (recommend **30%**) or fixed margin — and the starting number.
2. **Usage billing**: **prepaid credits** (recommended, safe) or postpay invoicing?
3. **Payment rails for v1**: build Stripe now, or ledger/invoice-preview only and add capture later?
