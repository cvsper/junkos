# Palm Beach County — Meta ads launch playbook

> Goal: buy the *first* real bookings in PBC and prove one full transaction
> loop, on the now-correct pixel `1785795592383973`. This is a **test to find
> cost-per-booking**, not a brand campaign.

## 🚦 Gate — do NOT launch until ALL true

Spending before a truck exists = paying to disappoint customers. Hold the line.

### Verified in code (2026-06-01)

- [x] **Browser pixel id correct** — `analytics.tsx` hardcoded fallback is `1785795592383973` (env `NEXT_PUBLIC_META_PIXEL_ID` overrides). ✅
- [x] **Server-side CAPI wired** — `backend/meta_capi.py` posts Purchase/Lead to the Graph API; `payments.py` fires `track_purchase(job_id=job.id, …)` from the Stripe webhook. Env-gated (`META_PIXEL_ID` + `META_CAPI_ACCESS_TOKEN`); silent no-op if unset. ✅
- [x] **Purchase dedup verified** — browser sends `eventID = purchase_<job.id>` (`trackBookingConversion`, where `bookingId = rawResult.job.id`); server sends `event_id = purchase_<job.id>`. **They match** → Meta dedupes browser + server Purchase into one conversion. ✅
  - ⚠️ Edge case: frontend falls back to `bookingResult.id || generateBookingId()` if `rawResult.job.id` is absent; in that degraded path the browser id would NOT match the server's real `job.id`. Normal path is fine.
- [x] **InitiateCheckout fires (browser)** — `book/page.tsx` calls `trackInitiateCheckout()` on reaching step 6 (payment). No server-side IC (browser-only is fine for IC). ✅
- [x] **Lead fires (browser)** — `book/page.tsx` calls `trackLead()` on funnel mount. ⚠️ Gaps: (a) browser `Lead` has **no `eventID`**, and there is **no server-side Lead call** in the booking flow, so Lead isn't deduped — acceptable since there's only one (browser) source today. (b) `meta_capi.track_lead()` exists but is **never called** from any route.
- [x] **capi-status health endpoint live** — `GET/POST /api/admin/capi-status/<secret>` added (gated by `ADMIN_SEED_SECRET`); reports `has_pixel_id`/`has_access_token`/`has_test_event_code` booleans + `meta_capi.status()`, never echoes secrets. `?test=1` fires a test Lead event.

### Verify in dashboard (outside repo)

- [ ] **≥1 committed hauler** can fulfill PBC jobs (from the call list / Sequence D)
- [ ] **Vercel `NEXT_PUBLIC_META_PIXEL_ID = 1785795592383973`** (or unset) — verified, redeployed — *verify in Vercel dashboard*
- [ ] **Render env** `META_PIXEL_ID` + `META_CAPI_ACCESS_TOKEN` set (+ optional `META_TEST_EVENT_CODE`) — hit `/api/admin/capi-status/<secret>` to confirm booleans — *verify in Render dashboard*
- [ ] **Events Manager** shows `Lead`/`InitiateCheckout`/`Purchase` firing from a live test booking, and Purchase shows **"Processed via both Browser and Server" / deduplicated** — *verify in Meta Events Manager*
- [ ] **Stripe checkout** completes end-to-end on the PBC landing/booking flow — *verify in dashboard/live test*

## Campaign structure (keep it boring)

| Setting | Value | Why |
|---|---|---|
| Objective | **Sales** (Leads if booking volume too low to optimize) | Optimize for money events, not clicks |
| Conversion event | `InitiateCheckout` first → switch to `Purchase` once ~15–20/wk | Booking volume too low for Purchase early; IC gives the algo signal |
| Budget | **$25/day**, ABO (not CBO) | Control at low spend; ~$175/wk buys real signal |
| Ad sets | **1** | Don't fragment a tiny budget |
| Schedule | 7-day test, don't touch days 1–4 (learning phase) | Editing resets learning |

## Audience

- **Geo:** tight radius around the committed hauler's base (e.g., WPB +12 mi, or the truck's actual zips) — *not* all of PBC. Match supply range.
- **Age/gender:** 35–65, all genders. Junk-removal buyers skew homeowner/mover.
- **Targeting:** **broad + Advantage+ audience ON.** At $25/day, good creative + clean pixel beats hand-built interest stacks. (Optional light signal: "Likely to move," "Homeowners.")

## Creative (this is where junk removal is won)

Run **3–5 creatives in the one ad set**, let it pick the winner. Formats: **9:16** (Reels/Stories) + **1:1** (Feed). Angles, in priority order:

1. **Before/after** — cluttered garage/yard → empty & clean. Single highest performer in this vertical. Static carousel or 5-sec video.
2. **UGC truck video** — phone-shot: truck pulls up, two guys haul a couch + mattress, "gone in under an hour." Authentic > polished.
3. **Instant-quote hook** — "Junk gone in Palm Beach — book in 60 seconds, pay online." Speaks to the funnel's actual advantage.
4. **Trust/local** — "Palm Beach's same-day junk removal. Licensed, insured, upfront pricing."

Primary text: lead with the pain ("Garage you can't park in?"), one line on speed + transparent price, CTA "Get your quote."

## Offer (converts cold traffic)

Launch promo — **"$25 off your first pickup"** or a fixed **single-item from $XX**. Wire it to the app's existing promo-code path (codes already forward to `createJob`). A first-order offer is the difference between a 1% and a 3% landing conversion.

## Landing / tracking

- Send to the **PBC landing page → booking funnel** (the working Stripe flow), not the homepage. SEO page exists: `pages/junk-removal/west-palm-beach-fl.html` (or platform booking).
- **UTM every ad:** `utm_source=meta&utm_campaign=pbc_launch&utm_content={creative}`.
- Judge on **cost per booking vs. job value.** PBC avg ticket is high (affluent: estate/reno/garage). If CAC < ~25% of AOV, scale. Ignore CTR vanity — watch cost-per-IC and cost-per-Purchase.

## Day-by-day

- **D1–4:** hands off (learning). Confirm events firing + spend pacing only.
- **D5:** kill any creative with CTR < ~1% or zero IC.
- **D7:** decision — cost-per-booking healthy → raise budget 20–30%/wk on the winner; bad → new creative angle, same structure. Never rebuild from scratch on one bad week.

## North star

One paid booking → fulfilled by your hauler → **5-star review + before/after photo.** That review/photo becomes your best ad creative *and* your SEO/GBP social proof. The first loop funds the flywheel.

---

## 🚀 GO-LIVE EXECUTION (verified 2026-06-14)

Plan above is complete. These are the *execution gates*, in order. Verified-in-code items are ✅; the rest are yours (dashboards / texts / Meta account).

### A. Dispatch pipeline — VERIFIED IN CODE ✅
Payment confirmed → job `confirmed` → `auto_assign_job_async` (background) → eligibility filter:
`is_online=True` AND `approval_status="approved"` AND `is_operator≠True` AND ≤30 mi AND truck_capacity≥volume AND no ±2h conflict. Default `DISPATCH_MODE="assign"` (top-3 score: distance .40 / rating .25 / capacity .20 / experience .15). No-show watchdog shipped (T-30 unassigned + T+15 late, every 5 min). **The dispatch path runs on Render and is independent of the server-side `umuve-booking-cascade.service` automation** (that unit failed 2026-06-14 04:08 UTC — triage separately; it does NOT block paid-booking dispatch).

### B. PBC25 promo — LIVE, ONE FIX NEEDED ⚠️
Validated against prod: `$25 fixed off, is_active=true, valid`. **BUT `min_order_amount=0.0`** — a small job nets near-free while you pay operator + Meta CAC. Tighten to $75 before spend (promo_id `5d03ed49-4e86-40c7-99a5-c0377094f5fb`):
```
PUT /api/admin/promos/5d03ed49-4e86-40c7-99a5-c0377094f5fb   (admin JWT)
{ "min_order_amount": 75 }
```
Or set it in the admin dashboard → Promos. Re-verify: `POST /api/promos/validate {"code":"PBC25","order_amount":60}` should then return `valid:false` (below min).

### C. Live config to verify (your dashboards / secret)
1. **No-operator alert chain** — `GET /api/admin/test-alert/<ADMIN_SEED_SECRET>` → expect `admin_phone_configured:true` AND/OR `admin_email_configured:true`, and you receive the test SMS/email. If both false → set `ADMIN_PHONE`/`ADMIN_EMAIL` on Render first (else paid bookings with no operator fail silently).
2. **CAPI** — `GET /api/admin/capi-status/<ADMIN_SEED_SECRET>` → `has_pixel_id` + `has_access_token` true.
3. **Vercel** `NEXT_PUBLIC_META_PIXEL_ID = 1785795592383973` (or unset).

### D. Supply online (your texts)
≥1 approved operator with `is_online=True` and a GPS ping within 30 mi of the target WPB radius. Operator: install Umuve Pro → log in → **Go Online** (sets token + `is_online` + GPS in one step). Confirm via admin dashboard → Contractors (online count ≥1 in WPB).

### E. E2E test booking (do this BEFORE ads)
Real booking on the PBC funnel → Stripe test/live → confirm in Meta Events Manager that `Lead` / `InitiateCheckout` / `Purchase` fire and Purchase shows **deduplicated (browser+server)** → confirm the job **dispatched to the online operator** (not the no-operator alert). One clean loop = green light.

### F. Ads on (your Meta account)
Build per "Campaign structure" above: Sales objective, optimize `InitiateCheckout`, **$25/day ABO, 1 ad set**, WPB +12 mi, 35–65 all, broad + Advantage+ ON, 3–5 creatives (assets in `marketing/creatives/`), UTM `utm_source=meta&utm_campaign=pbc_launch&utm_content={creative}`, land on the PBC booking funnel. Hands-off D1–4.

**Critical path: B → C → D → E → F.** A/no-show watchdog already done.
