# Umuve Pricing Upgrade & Anti-Leakage Plan

> Authored 2026-06-09. Grounded in a full code audit of the live pricing/payment/dispatch
> system. Decisions locked with sevs: **tiered pricing**, **photo-quote-first booking**,
> **auth-and-capture payments**, goal = **plug leakage + max revenue/job + operator retention**
> (subscription ARR parked for now).

---

## 0. Source-of-truth audit (what exists today)

| Concern | Where | Today's behavior |
|---|---|---|
| Pricing engine | `backend/routes/booking.py:408` `calculate_estimate()` | `(items − vol_discount) × surge + 8% service fee + recycling + labor`, floor $79 |
| Item catalog | `booking.py:40-107` `CATEGORY_PRICES` | ~100 items, ~25% under 1-800-GOT-JUNK |
| Truck-load path | `booking.py:117` `TRUCK_LOAD_PRICES`, `/api/booking/estimate-load` | $99 min → $579 full; arbitrageable vs item path |
| Volume discount | `booking.py:177` | 4–7 items 10%, 8–15 15%, 16+ 20% |
| Surge | `booking.py:188-190` + `SurgeZone` table | same-day +25%, next-day +10%, weekend +15%, zone × |
| Labor fee | `booking.py:172` `LABOR_FEE_PER_HOUR=$55` | **DEAD — hardcoded to 0 in calculate_estimate** |
| Vision photo quote | `backend/routes/quotes.py` | binding @ 0.85 confidence, 48h TTL — **built, not default path** |
| Payment | `backend/routes/payments.py` | **immediate capture** (auth-and-capture helpers in `payment_auth_capture.py` exist, unused) |
| Commission | `payments.py:25` = 20% + 8% service = **28% effective** | inconsistent w/ `models.py:140`=15% & "85%" marketing |
| On-site adjust | `drivers.py:683`, `operator.py:606` | **down = auto-approved silently; up = needs customer approval (backwards)** |
| Completion proof | `drivers.py:396`, `Step2Photos.jsx` | photos **optional/skippable**; payout fires on 'completed' |

### Three leakage vectors (not one)
- **A. Customer under-declares** — "1 sofa $89" w/ a truckload. No qty ceiling, photos skippable.
- **B. Off-platform cash deal** — operator phone exposed to customer at assignment (`models.py:90`, `jobs.py:198`); overflow settled in cash.
- **C. Operator silent skim** — downward volume adjust auto-approved, no customer notice, Stripe quietly reduced (`drivers.py:729-748`).

---

## P0 — Reconcile the numbers (blocker, ~0.5 day)
Can't tune pricing on inconsistent constants.
- [ ] Pick the true commission. Make it the single source of truth (one constant, imported everywhere). Recommend **20% platform + transparent service fee**, OR collapse to one blended number.
- [ ] Fix `models.py:140` default (0.15) to match.
- [ ] Fix `email_templates.py:938` ("Umuve takes 15%") and the landing "85% to operator" claim to reflect reality.
- [ ] Add a unit test asserting commission constants agree across modules.

---

## Phase 1 — Plug the leakage (highest priority)

### 1.1 Auth-and-capture (the core fix) — ~2-3 days
- [ ] Wire `payment_auth_capture.py` into the booking → completion flow.
- [ ] At booking: **authorize** `estimate + one-truck-tier buffer` (not capture).
- [ ] At verified completion: **capture** the photo-confirmed final amount. Release the rest.
- [ ] Defuses A (can't under-pay below verified) and C (captured = verified, not operator's claim).

### 1.2 Mandatory proof gate — ~1-2 days
- [ ] Remove "Skip for now" on before-photos (`Step2Photos.jsx:81`).
- [ ] Hard gate: no before-photo + volume confirmation → cannot mark complete → no payout (`drivers.py:491`).
- [ ] Store `proof_submitted_at` + photo URLs as a completion precondition, not a warning.

### 1.3 Flip the adjustment incentive — ~1 day
- [ ] **Down-adjustment** now requires customer confirmation + photo proof (currently silent auto-approve).
- [ ] **Up-adjustment** within authorized buffer: smooth, instant, operator earns split immediately.
- [ ] **Notify customer on ANY change**, up or down. Add `adjusted_by` audit field (who proposed it).
- [ ] Files: `drivers.py:683-802`, `operator.py:606-649`, `models.py:289`.

### 1.4 Reduce contact-exposure surface — ~0.5 day
- [ ] Delay operator phone exposure until job is in-progress (or mask via proxy number). Keep in-app chat as the primary channel (already masked/job-scoped — good).
- [ ] File: `models.py:90` (user.to_dict in contractor payload), `jobs.py:198`.

---

## Phase 2 — Max revenue per job + tiered pricing + photo-first funnel

### 2.1 Wire labor + access surcharges (pure left-on-table) — ~1-2 days
- [ ] Activate `labor_fee` in `calculate_estimate` (currently 0). Trigger on stairs / long-carry / disassembly flags.
- [ ] Add **access surcharge**: curbside (free) vs inside / upstairs / 2nd-floor+ tier. Biggest real cost driver, currently uncaptured.
- [ ] Surface these as line items at on-site confirmation so they're transparent, not bait-and-switch.

### 2.2 Tiered price position — ~1 day
- [ ] Keep $89 single-item hero (acquisition).
- [ ] Re-benchmark big loads (½ truck+) toward **~15% under** competitors (from 25%). ~13% more on the jobs where the work actually is.
- [ ] Update `TRUCK_LOAD_PRICES` + the larger `CATEGORY_PRICES` accordingly. Keep small items aggressive.

### 2.3 Reconcile item-vs-volume arbitrage — ~1 day
- [ ] When both paths apply, quote `MAX(item-based, volume-based)` — stop customers shopping the cheaper path for the same junk.
- [ ] Align item-min ($79) and truck-min ($99) logic.

### 2.4 Photo-quote-first funnel (also kills under-declaration) — ~2-3 days
- [ ] Make vision-AI photo quote (`quotes.py`) the **default** booking entry. "Snap your pile → binding price."
- [ ] Item-picker becomes the fallback for known single items.
- [ ] Binding quote locks honest pricing; a photo is far harder to undercount than a dropdown.
- [ ] **NOTE: invoke `frontend-design` skill before building any of this UI.**

---

## Phase 3 — Operator retention (make the cash deal irrational)

### 3.1 Loyalty commission tiers — ~2 days
- [ ] Tier operator commission by verified GMV: 20% → 15% → 12% at volume thresholds.
- [ ] The side-deal now costs them future earnings. Store tier on contractor; recompute monthly.

### 3.2 Instant payout — ~1-2 days
- [ ] Same-day / instant Stripe Connect transfer on verified completion (you already do `stripe.Transfer.create`).
- [ ] Kills cash's only real edge: speed.

### 3.3 Priority dispatch tied to standing — ~1 day
- [ ] Operators who run clean, verified, in-app volume get dispatch priority. Platform flow > one-time skim.

---

## Phase 4 — Detection (ongoing)
- [ ] Wire `ops_classifier.py` / `ops_decision_agent.py` to leakage signals:
  - operators clustering at minimum volume
  - high downward-adjustment rate
  - single-item bookings in known big-job zips
  - repeat customer + single-item + 5-star (overflow-settled-cash signal)
- [ ] Flag → review → warn → deactivate ladder. Account standing/rating = the asset they lose.

---

## Sequencing summary
1. **P0** numbers reconcile (blocker)
2. **Phase 1** leakage — auth-capture, proof gate, flip adjustment, contact masking
3. **Phase 2** revenue — labor/access fees, tiered pricing, photo-first funnel
4. **Phase 3** retention — loyalty tiers, instant payout, priority dispatch
5. **Phase 4** detection — anomaly wiring

Parked: subscription/recurring ARR (`portal_recurring.py`, `billing_portal.py`) — revisit after the above.
