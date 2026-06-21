# Umuve — Session Handoff (2026-06-21)

> Written for another agent (e.g. Codex) to pick up cleanly. Covers everything
> shipped in this session: what changed, where (file refs), what's deployed vs.
> still needs config, and the gotchas. All work is on `main` of
> `github.com/cvsper/junkos` and pushed.

---

## 0. Orientation — which app is which (READ FIRST)

This monorepo has several frontends. Getting this wrong wastes hours:

| Path | What it is | Deploys to |
|---|---|---|
| **`platform/`** | **Next.js customer booking app — THE LIVE FUNNEL** | **app.goumuve.com** |
| `landing-page-premium/` | Static marketing site + SEO pages | goumuve.com |
| `portal/` | Next.js **B2B portal** (orgs/properties/recurring/invoices) | portal.goumuve.com |
| `customer-portal-react/` | **DEAD** Vite app — NOT deployed. Do not edit. | — |
| `JunkOS-Driver/` | iOS operator app "Umuve Pro" (`com.goumuve.pro`) | App Store / TestFlight |
| `backend/` | Flask API (gunicorn+eventlet) | **junkos-backend.onrender.com** (Render service `umuve-backend`, id `srv-d64bqtffte5s73841geg`) |

- Backend **auto-deploys on push to `main`** (Render). Health: `GET /api/health`.
- `platform/` and `portal/` auto-deploy on Vercel (platform confirmed working).
- iOS: `cd JunkOS-Driver && ./archive-and-upload.sh` (xcodegen → archive → upload via `ExportOptions.plist` which is set to `destination: upload`). Mapbox makes archives ~3GB of DerivedData — keep disk clear.
- ASC API helper: `JunkOS-Driver/app-store/asc.py` (gitignored — holds key/issuer ids). `python3 asc.py audit|state|setmeta|screenshots`.

---

## 1. Render infra cleanup (cost: ~$80.57 → ~$15/mo)

Deleted duplicate/dead services + folded the worker into the web:
- **Consolidated** the Celery worker + Redis into the web's APScheduler (`backend/scheduler.py` — now 13 jobs incl. the migrated portal/customer tasks + the new broadcast sweep). `backend/render.yaml` no longer declares a worker or redis; `REDIS_URL` removed (Flask-Limiter → `memory://`, ops_event_bus → inline).
- **Deleted** (via Render API): `umuve-backend-plrk`, `umuve-portal-beat`, `umuve-portal-beat-plrk`, `umuve-redis`, `umuve-redis-plrk`, `umuve-db-plrk`, `proxo-api`, `proxo-db`, `trendcart-ai`.
- **Live stack kept:** `umuve-backend` (free), `umuve-db` (the DB with real data — `dpg-d67mjqemcj7s739gnv60-a`).
- Webhook reconciliation note: `REDIS_URL` was removed from the live web env via API; the web redeployed healthy on the memory:// fallback before redis deletion.

**Still the user's to do:** downgrade the Render **team seat** Professional→Hobby (−$19, billing UI). Other side-projects (`memoralabs-api`, `sandhill-portal-api`, `proxell`+`proxell-db`) left intact.

---

## 2. Umuve Pro iOS (App Store)

- App `com.goumuve.pro`, ASC app id **6759131650**, team `24GH82AX9R`, ASC key `3MXH45MMJ6`.
- **build 37** = iPhone-only (`TARGETED_DEVICE_FAMILY=1` on the target — xcodegen injects a target-level `1,2` default that overrides project-level, so it must be on the target), VALID, **submitted to App Store review** (version 1.0). Metadata, 6 screenshots (6.5" `APP_IPHONE_65`, designed + rendered via `app-store/screenshots/index.html`), App Privacy, pricing (Free), copyright `2026 Umuve LLC`, review notes all set via `asc.py`.
- **build 38** = in-app broadcast offer-accept (#51 iOS). VALID, in TestFlight.
- **build 39** = operator instant cash-out UI (#57). VALID, in TestFlight.
- Demo review account: `applereview@goumuve.com` (provisioned approved + non-null `stripe_connect_id` so it clears the `StripeConnectOnboardingView` wall; see `backend/scripts/setup_review_account.py`).
- `ExportOptions.plist` fixed `destination: export → upload` (it previously only wrote the IPA to disk, never uploaded — the script's "uploaded" message was misleading).

**Still the user's to do:** ship builds 38/39 in a 1.0.1 update; App Privacy nutrition label + Sign-In demo creds were entered in ASC UI.

---

## 3. Growth program ("all tiers") — Tasks #46–57

All backend deployed + health-verified; frontends on the correct apps. **Key correction mid-session:** promo/pixel/abandon were first written into the DEAD `customer-portal-react`, then reverted (`2da87e5`) and re-confirmed against the real `platform/` app (which already had the frontend halves wired — the backend was the missing piece).

### Tier 1 — funnel/revenue integrity (live)
- **#46 Promo apply** (`backend/routes/payments.py`): promo codes were validated but never reduced the charge. Now `create-intent` + `create-intent-simple` re-validate server-side and subtract the discount; `confirm` + `confirm-simple` + the webhook increment `promo.use_count` once. `platform/` already sent `promo_code`. `PBC25` = **fixed $25 off, min $200**.
- **#47 Funnel analytics** (`backend/meta_capi.py`, `platform/src/components/analytics.tsx`): added server-side `track_initiate_checkout` (event_id `checkout_<job_id>`); the booking app had NO browser pixel before (only SEO pages did) — confirmed `platform/` has its own pixel/PostHog/GA. Note the booking-app pixel I added to `customer-portal-react/index.html` is dead (reverted).
- **#48 Abandoned capture**: `platform/` already beacons `/api/booking/abandoned`; backend endpoint + the drip runner (now in APScheduler) complete the loop.
- **#49 Webhook idempotency** (`backend/routes/payments.py` `_handle_payment_succeeded`): early-return if already `succeeded` so Stripe retries don't resend emails / double-count.
- **#50 No-show watchdog**: confirmed already scheduled (`scheduler.py` id `noshow_watchdog`). Needs `ADMIN_PHONE`/`ADMIN_EMAIL` on Render or alerts are silent.
- **#55 Server-authoritative charge** (`create-intent-simple`): was trusting the client `amount` (pay-$1 hole). Now derives the charge from `job.total_price − job.discount_amount` when a booking exists; logs a warning on mismatch; falls back to client amount only pre-booking.

### Tier 2
- **#52 Tracking trust signals**: `backend/routes/tracking.py` `/api/tracking/code/<code>` now returns `before_photos`/`after_photos` (on_site/complete) + hauler `total_jobs`; rendered in `platform/src/components/tracking/guest-tracking.tsx`.
- **#51 In-app broadcast offer-accept** (builds 38): backend `GET /api/driver/offers` (`routes/driver.py`) + existing atomic `POST /api/offers/<token>/accept` + `dispatcher.sweep_expired_broadcasts()` (scheduled, re-broadcasts expired-unclaimed jobs, capped ~32 offers then escalates). iOS: `OfferModels.swift`, `DriverAPIClient.getOffers/acceptOffer`, JobFeed "Job offers" section. **Unblocks `DISPATCH_MODE=broadcast`.**
- **#56 InitiateCheckout dedup** (`platform/`): browser event now fires from the payment step with `eventID checkout_<bookingId>` to dedupe with the server CAPI event (was double-counting).

### Tier 3 — B2B recurring monetization (#53, all 6 stages, live)
See `docs/b2b-recurring-plan.md`. The engine was ~80% built; this wired the gaps:
- **S1** contract pricing: recurring jobs were created with NO price → $0 invoices. `models.active_contract_for_org()`; `portal_recurring.py` prices each job at the contract per-pickup rate; `portal_invoicing.py` bills `monthly_base + overage beyond included_pickups` (falls back to summing job prices when no contract — preserves the existing test).
- **S0** `POST /portal/v1/billing/bootstrap` (admin-guarded) → `billing_portal.bootstrap()` creates Stripe tier products/prices.
- **S2** `billing_portal.push_portal_invoice_to_stripe()` creates+finalizes a Stripe invoice (send_invoice on net terms) per `PortalInvoice`, stores `stripe_invoice_id`; the `/portal/v1/billing/webhook` already flips paid/past_due.
- **S3** self-serve: `create_checkout_session` + `create_billing_portal_session` + routes `POST /portal/v1/billing/checkout` and `/billing/portal-session` (org-scoped, owner/admin); webhook handles `checkout.session.completed` to capture customer+subscription onto the org.
- **S4** portal UI: `portal/app/settings/page.tsx` Subscribe (per-tier) + Manage-billing buttons.
- **S5** guardrails: `portal_recurring.py` holds job-gen for `past_due/paused/churned` orgs; webhook sets org `past_due` + sends `email_templates.b2b_dunning_html` on `invoice.payment_failed`.

### Tier 4
- **#54 Positioning & moat brief**: `marketing/positioning-moat.md` (vision-pricing flywheel + Maya voice as the two un-copyable moats; B2B recurring as the durable revenue).

### #57 — Operator instant cash-out (build 39)
Backend `/api/payments/payout/eligibility` + `/payout/instant` (`stripe.Payout.create(method="instant")`, operator bears the 1.5% fee) already existed; build 39 adds the Earnings-screen "Cash Out" card: **instant (~30 min, 1.5% fee) or free automatic (1–2 business days)**. Instant requires the operator to link a **debit card** to their Express account.

---

## 4. CONFIG THE USER MUST DO TO ACTIVATE (none of this is code)

1. **Umuve Pro #51:** ship build 38/39 (1.0.1) → set `DISPATCH_MODE=broadcast` on Render (currently `assign`; broadcast was held precisely because the app couldn't claim offers — now it can).
2. **B2B #53:** run `POST /portal/v1/billing/bootstrap` (admin JWT) → register the **portal** Stripe webhook at `/portal/v1/billing/webhook` (events `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`) → set **`STRIPE_WEBHOOK_SECRET_PORTAL`** on Render (SEPARATE from the payments webhook secret) → enable the Stripe Customer Portal in the Stripe dashboard.
3. **Payments webhook:** register `/api/webhooks/stripe` (payments) + set `STRIPE_WEBHOOK_SECRET` — makes payment reconciliation reliable (#49).
4. **Alerts:** set `ADMIN_PHONE` / `ADMIN_EMAIL` on Render (#50 no-show alerts).
5. **Render team seat** → Hobby (−$19).
6. **Security (urgent):** rotate the **Render API key** and **prod DB password** — both were pasted in chat this session.

---

## 5. Gotchas / facts worth knowing
- `umuve-db` external host: `dpg-d67mjqemcj7s739gnv60-a.oregon-postgres.render.com` (needs `sslmode=require`).
- Take-rate: 20% platform commission + 8% service fee (`backend/routes/payments.py`).
- Pricing engine: `backend/routes/booking.py:calculate_estimate` (84-SKU item pricing + volume/surge) and `backend/routes/quotes.py` (vision photo→binding quote, <5s).
- Maya = Vapi voice agent (`backend/vapi_setup.py`).
- iOS: no simulators installed on the build machine; screenshots are designed/rendered, not simulator captures.

## 6. Full commit list (this session, on `main`)
```
bf91ea7 Operator instant cash-out UI (build 39)
eaee192 #56: dedup browser InitiateCheckout with server CAPI
95b3d90 #51 (iOS): in-app broadcast offer list + accept (build 38)
7618b7c #51 (backend): in-app offer list + broadcast second-wave
51c068e #53 Stage 4: portal billing UI — subscribe + manage billing
78275dd #53 Stage 5: past-due holds + dunning on failed payment
9a8fb1b #53 Stage 3: self-serve subscribe via Stripe Checkout + Customer Portal
df7f382 #53 Stage 2: push monthly invoices to Stripe to actually collect
cddccb1 #53 Stage 0: guarded admin route to bootstrap Stripe billing tiers
449c08c #53 Stage 1: enforce contract pricing on recurring jobs + invoices
10ae377 docs(#53): staged B2B recurring monetization plan
0da216f T2: before/after photos + hauler social proof on the track page
2da87e5 Revert promo/pixel/abandon edits from the dead Vite app
43e11f3 T4: Positioning & moat brief
fb4d768 T2: Surface before/after photos + hauler social proof in tracking
61f252c T1+: Make create-intent-simple charge server-authoritative
17b7a21 T1: Trigger abandoned-booking capture from the funnel
c338c8e T1: Make Stripe payment webhook idempotent + count promo on reconcile
49b84f6 T1: Funnel analytics — InitiateCheckout (server CAPI + browser) + pixel
e0bbdee T1: Apply promo codes to the actual charge (was cosmetic)
c80e512 Fix Umuve Pro upload + review-script SSL
4cccd69 Umuve Pro: iPhone-only (build 37) + review-account setup script
(+ this handoff doc, the consolidation, screenshots, and vercel.json fix earlier)
```
