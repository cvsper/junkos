# Umuve — Positioning & Moat (Tier 4)

> Why Umuve wins, and the two assets competitors can't copy. Written 2026-06-21.
> Audience: ad copy, App Store/landing messaging, investor/partner narrative,
> and product prioritization.

## The one-line position
**"The junk-removal app that prices itself."** Snap a photo or say it out loud —
get an honest, binding price in seconds, then watch your hauler show up. No
call-for-a-quote, no "the driver will assess on arrival," no surprise upcharge.

## The competitive field (and why the wedge exists)
| Competitor | How you get a price | Gap Umuve exploits |
|---|---|---|
| 1-800-GOT-JUNK / College Hunks | Truck shows up, *then* quotes you | No price until they're at your door; pressure to accept |
| LoadUp / Dolly | Form or in-app, often a range | Estimates, not binding; still call-heavy |
| Local haulers (Thumbtack, FB) | Phone tag, text photos, haggle | Slow, opaque, no tracking, no guarantee |

Every incumbent makes the customer *work to learn the price.* That friction is
the wedge. Umuve collapses quote→book→track into one app flow.

## The two moats (un-copyable, compounding)

### 1. The vision-pricing flywheel
Umuve already does photo → item/volume detection → **binding** quote in <5s
(`routes/quotes.py`, `VisionInferenceLog` captures model, tokens, latency, cost,
and raw output for every quote). The asset isn't the LLM call — anyone can call
an LLM. The asset is the **calibration loop**: every quote → actual job →
operator's real volume adjustment (`VolumeAdjustmentViewModel`) is a labeled
training pair tying *a photo of a pile* to *what it actually cost to haul.*
- **Why it compounds:** the more jobs, the tighter the photo→price model, the
  more confidently Umuve can quote binding prices competitors won't risk. A new
  entrant starts at zero labeled pairs.
- **Moves:** (a) close the loop in code — feed operator volume adjustments +
  final price back as calibration; (b) raise the binding-confidence threshold as
  data grows (more binding quotes = higher conversion); (c) surface "binding
  price — guaranteed" as the headline trust signal.

### 2. Maya — voice booking
Maya books a junk-removal job over the phone in ~90s (`vapi_setup.py`: quote,
create booking, check service area, send checkout text — all by voice). No
competitor lets a customer *call a number and have an AI book + price the job.*
- **Why it matters here:** junk removal skews older / less app-native (estate
  cleanouts, downsizing seniors, property managers between tenants). Voice is the
  on-ramp the app-only competitors miss.
- **Moves:** (a) put Maya's number on every SEO page + Google Business Profile as
  "call for an instant quote"; (b) inbound-call → booking is a measurable funnel
  (CallLog logs sentiment + booking_created) — optimize it; (c) Maya outbound for
  B2B follow-up and win-back (review_scheduler already does Vapi calls).

## Trust = the third pillar (table stakes, but Umuve under-uses what it has)
High-trust transaction (a stranger hauling from your home). Umuve already
*stores* the trust artifacts but barely *shows* them:
- Before/after photos (now exposed in tracking — #52) → make them the proof in
  the post-job email + review request.
- Live tracking by code, hauler rating + job count (now in tracking response).
- **Add a satisfaction guarantee** ("re-haul or refund if it's not right") — none
  of the local haulers offer it; cheap to promise, big conversion lift.

## Where the durable revenue is: B2B recurring (see Tier 3 / #53)
Consumer one-offs fund the lights. **Property managers, realtors, apartment
turnovers, construction, estate firms** = recurring, predictable, higher-LTV,
and stickier (switching cost once you're their default hauler). The recurring
engine is built (orgs, properties, units, schedules, invoicing); wiring billing
is the single biggest ceiling-raiser. The moats above are the *wedge*; B2B
recurring is the *business*.

## Messaging cheat-sheet (use verbatim in ads / store / landing)
- Headline: **"Know the price before they show up."**
- Sub: "Snap a photo or call — binding quote in seconds. Booked, tracked, done."
- Proof line: "See your hauler, their rating, and before/after photos — in one app."
- B2B: "One default hauler for every turnover. Recurring pickups, monthly invoice."

## Prioritization implication
Don't out-feature the incumbents — **out-price-transparency** them. Every
roadmap item should serve one of: (1) faster/more-confident binding quotes,
(2) the voice on-ramp, (3) visible trust, (4) B2B recurring. If a feature serves
none of these, it's not a moat — it's a distraction.
