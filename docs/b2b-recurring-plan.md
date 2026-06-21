# #53 — B2B Recurring Monetization: Staged Plan

> The highest-LTV play (property managers, realtors, apartment turnovers,
> construction, estate firms = predictable MRR). Grounded scan 2026-06-21:
> the engine is ~80% built. This is wiring + 3 real gaps, not a rebuild.
> Each stage is independently shippable (build → test → deploy → verify).

## What already exists (verified)
- **Models** (`portal_v1_models.py`, `models.py`): `Org` (tier, status, stripe_customer_id, stripe_subscription_id, net_terms_days), `Contract` (monthly_base_cents, metered_per_pickup_cents, metered_per_ton_cents, included_pickups, pricing_overrides JSON), `OrgMember` (roles/scopes), `PortalProperty`, `PortalUnit`, `PortalRecurringSchedule`, `PortalInvoice` + `PortalInvoiceLineItem`.
- **Recurring job-gen** (`portal_recurring.py::generate_jobs_for_due_schedules`) — now scheduled in the web's APScheduler (done this session).
- **Monthly invoicing** (`portal_invoicing.py::generate_monthly_invoices`) — generates PortalInvoice + line items; scheduled.
- **Stripe billing** (`billing_portal.py`): `bootstrap()` (create products/prices per tier), `subscribe_org()` (customer + subscription), webhook intent for invoice.paid / payment_failed / subscription.updated. `billing_portal_bp` registered (server.py:261).
- **Portal app** (`portal/app/`): login, dev-login, properties, team, jobs, recurring, invoices, settings, invite pages.
- **API** (`routes/portal_v1.py`): properties/units CRUD, recurring CRUD, ESG settings/report, audit; `routes/portal.py` billing read-only.

## The 3 real gaps
1. **Contract pricing is NOT applied** — `portal_recurring.py` creates jobs at default residential pricing, ignoring the org's `Contract` (per-pickup rate, overrides). B2B jobs are mispriced.
2. **Invoices don't actually charge** — `PortalInvoice` rows are generated but not pushed to Stripe; the billing webhook isn't confirmed wired/registered. Money isn't collected.
3. **No self-serve onboarding** — `subscribe_org()` is only invoked admin/CLI-side (server.py:601); a PM can't sign up → pick tier → pay → go live on their own.

---

## Stage 0 — Audit & config (~0.5 day)
**Goal:** confirm live state, no code.
- Run `billing_portal.bootstrap()` against prod Stripe → create/verify tier products + prices; record price IDs.
- Register the B2B billing webhook endpoint in Stripe + set its secret (separate from the payments webhook).
- Walk every `portal/app` page logged in as a real org (not dev-login); note what's wired vs stubbed.
- **Done when:** a confirmed punch-list + Stripe tier prices exist.

## Stage 1 — Contract pricing enforcement (~1 day) [depends: 0]
**Goal:** B2B jobs priced by the org's contract, not residential.
- `portal_recurring.py`: when generating a Job for a schedule, resolve the org's active `Contract` and price the pickup at `metered_per_pickup_cents` (and apply `pricing_overrides` by item where present); fall back to residential only if no contract.
- `portal_invoicing.py`: ensure line items reflect contract pricing + `monthly_base` + overage past `included_pickups`.
- **Done when:** a recurring schedule under a Pro contract generates jobs at the contract rate; the month's invoice = base + (pickups − included) × per-pickup, verified on a test org.

## Stage 2 — Invoice → Stripe billing + webhook (~1–1.5 days) [depends: 1]
**Goal:** invoices actually collect money.
- Decide the model per tier: **subscription** for `monthly_base` (via `subscribe_org`) + **metered/invoice-items** for per-pickup overage (Stripe invoice items appended to the monthly invoice).
- Wire `generate_monthly_invoices` → create/finalize a Stripe invoice (or usage records) for each org; store the Stripe invoice id on `PortalInvoice`.
- Wire the billing webhook: `invoice.paid` → `PortalInvoice.status=paid` + `Org.status=active`; `invoice.payment_failed` → `past_due` + dunning email; `customer.subscription.updated` → sync tier/status.
- **Done when:** month rollover charges the org's card on file and the webhook flips the invoice to paid; a failed charge sets past_due.

## Stage 3 — Self-serve onboarding + subscribe (~1 day) [depends: 2]
**Goal:** a PM signs up and goes live without admin.
- Public org-signup route (create Org + owner OrgMember) → tier selection → **Stripe Checkout** (or Customer Portal) to capture payment → `subscribe_org()` on success.
- Expose `subscribe_org` + a Stripe Customer Portal link via `billing_portal_bp` routes.
- `portal/app` onboarding flow + real auth (retire dev-login for prod).
- **Done when:** a new PM creates an org, subscribes, and can add properties/schedules — end to end.

## Stage 4 — Portal UI completeness + polish (~1 day) [depends: 3]
**Goal:** the full loop works in the UI, on-brand.
- Properties/units, recurring schedules, team/invite, and invoices (list + status + pay/download) pages fully wired to the API under real auth.
- Invoice page shows status, Stripe-hosted invoice/receipt link, and a "pay now" for past_due.
- **Done when:** a PM runs add-property → schedule recurring → see generated jobs → view/pay invoice, all in the UI.

## Stage 5 — Guardrails: dunning + credit holds (~0.5 day) [depends: 2]
**Goal:** protect revenue.
- `past_due` org → block new recurring job generation until resolved (check in `portal_recurring.py`).
- Dunning email sequence on `payment_failed`; admin override to clear holds.
- **Done when:** a past_due org's schedules pause; paying resumes them.

---

## Effort & sequencing
~**4.5–5.5 focused days**, shippable per stage. Critical path: 0 → 1 → 2 → 3 → 4; Stage 5 can run alongside 4. Stages 1 and 2 alone make B2B revenue real (correct pricing + actual collection) even before self-serve.

## GTM tie-in (see `marketing/positioning-moat.md`)
Target property managers / realtors / turnover companies with "one default hauler,
recurring pickups, one monthly invoice." Land 1–2 anchor accounts manually
(concierge) during Stage 1–2 to validate pricing before building self-serve (3–4).
