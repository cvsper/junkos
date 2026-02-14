# Phase 3: Payments Integration - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Customer pays upfront via Stripe (held in escrow), driver receives 80% payout on job completion. Covers: Stripe payment sheet in customer app, escrow/hold mechanics on backend, Stripe Connect onboarding for drivers, driver earnings dashboard, and payout status tracking. Dispatch, job matching, and real-time tracking are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Payment Flow UX
- Payment happens BEFORE job creation — no job exists without successful payment
- Fresh card entry each booking (no saved cards for MVP)
- Use Stripe's native Payment Sheet (Apple Pay + card entry) — no custom card form
- Payment sheet appears after the existing Review step as the final action before job creation

### Post-Payment Confirmation
- Claude's discretion on confirmation UI — should fit naturally with the existing success overlay pattern from Phase 2

### Driver Earnings Experience
- Detailed breakdown: per-job earnings list with dates, amounts, and payout status, plus summary totals (today, this week, all-time)
- Show driver's 80% take only — do NOT show the full job price or commission deduction
- Full earnings history (all time) with date range filters: today, this week, this month, custom
- Each job shows payout status: Pending → Processing → Paid

### Stripe Connect Onboarding
- Use SFSafariViewController (in-app browser) for Stripe Connect onboarding flow
- Stripe Connect setup is REQUIRED as part of initial driver signup — prompted right after sign-in, before accessing the app
- Block driver from job feed entirely until Stripe Connect setup is complete — show a setup-required screen
- Settings shows payout status badge (Not set up / Pending verification / Active) with action button to complete or update setup

### Claude's Discretion
- Post-payment confirmation UI design (overlay vs screen — match existing patterns)
- Exact earnings dashboard layout and typography
- Error handling for payment failures (card declined, network issues)
- Stripe webhook handling architecture
- Escrow release timing and mechanics

</decisions>

<specifics>
## Specific Ideas

- Payment flow: Review step → Stripe Payment Sheet → job creation. Single linear path, no branching.
- Driver onboarding: Sign in → Stripe Connect setup (mandatory) → app access. No skipping.
- Earnings should feel informative but not overwhelming — driver's take only, no commission math shown.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-payments-integration*
*Context gathered: 2026-02-14*
