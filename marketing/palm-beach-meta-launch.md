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
