# Meta Ads Campaign — Customer Acquisition

## Campaign Overview

**Objective:** Drive junk removal bookings from South Florida homeowners
**Platform:** Meta (Facebook + Instagram)
**Budget:** $15-25/day to start ($450-750/month)
**Goal:** 20-40 bookings/month at $10-18 CPA
**Pixel:** Meta Pixel on goumuve.com (verify installed)
**GA4:** G-CLGPJ5TS3G

---

## Campaign Structure

### Campaign 1: "Book a Pickup" — Conversions (Primary)

**Objective:** Conversions (optimize for Lead or Purchase)
**Budget:** $15/day

#### Ad Set 1: Palm Beach County Homeowners
- **Location:** Palm Beach County, FL (25mi radius from West Palm Beach)
- **Age:** 25-65+
- **Interests:** Home improvement, DIY, Moving, Real estate, Decluttering, Marie Kondo, Home renovation
- **Behaviors:** Homeowners, Recently moved
- **Placements:** Automatic (Facebook Feed, Instagram Feed, Stories, Reels)

#### Ad Set 2: Broward County Homeowners
- **Location:** Broward County, FL (25mi radius from Fort Lauderdale)
- **Same targeting as Ad Set 1**

#### Ad Set 3: Miami-Dade (expansion, add after 2 weeks if CPA < $15)
- **Location:** Miami-Dade County, FL
- **Same targeting**

---

### Campaign 2: "Retargeting" — Conversions (Secondary)

**Objective:** Conversions
**Budget:** $5/day

#### Ad Set 1: Website Visitors (7 days)
- **Audience:** Custom audience — visited goumuve.com in last 7 days, didn't book
- **Frequency cap:** 3 impressions/day

#### Ad Set 2: Abandoned Bookings
- **Audience:** Custom audience — started booking flow but didn't complete
- **Offer:** 10% off with code COMEBACK10

---

## Ad Creatives

### Creative 1: "Before/After" (Static Image)
**Format:** 1080x1080 square
**Visual:** Split image — cluttered garage on left, clean garage on right
**Headline:** Junk Gone in 24 Hours
**Primary text:**
> Got junk? We'll haul it away — fast. Starting at $119.
> Same-day service available across Palm Beach & Broward.
> Book online in 2 minutes. No hidden fees.
**CTA:** Book Now
**URL:** https://goumuve.com/book

### Creative 2: "Price Anchor" (Static Image)
**Format:** 1080x1080 square
**Visual:** Clean, branded graphic with pricing
**Headline:** Junk Removal from $119
**Primary text:**
> Cheaper than 1-800-GOT-JUNK. Faster than doing it yourself.
> Furniture, appliances, yard waste, garage cleanouts — we haul it all.
> Licensed & insured. Same-day pickups available.
**CTA:** Get a Quote
**URL:** https://goumuve.com/book

### Creative 3: "Social Proof" (Carousel)
**Format:** 1080x1080 carousel (3-4 cards)
- Card 1: "500+ Pickups Completed in South Florida"
- Card 2: Customer quote — "They showed up same day and cleared my entire garage. Amazing." — Maria R., Boca Raton
- Card 3: "Rated 4.9 stars by South Florida homeowners"
- Card 4: "Book in 2 minutes — from $119" + CTA
**Primary text:**
> South Florida's #1 junk removal service. Here's why:
**CTA:** Book Now

### Creative 4: "Quick Video" (Reels/Stories — 15s)
**Format:** 9:16 vertical video
**Script:**
- [0-3s] POV: You looking at a pile of junk in your garage
- [3-7s] Text overlay: "One tap. Gone tomorrow."
- [7-12s] Quick cuts of haulers loading truck, before/after
- [12-15s] Logo + "Book now at goumuve.com — from $119"
**CTA:** Book Now

### Creative 5: "Retargeting — Urgency" (Static)
**Format:** 1080x1080
**Visual:** Clean branded graphic
**Headline:** Still thinking about it?
**Primary text:**
> You checked us out — so you know the junk needs to go.
> Book today and get 10% off your first pickup.
> Use code: COMEBACK10
**CTA:** Book Now
**URL:** https://goumuve.com/book

---

## Conversion Tracking Setup

1. **Meta Pixel** — Must be installed on goumuve.com (verify status)
2. **Standard Events to track:**
   - `PageView` — all pages
   - `ViewContent` — /book page
   - `InitiateCheckout` — booking form started
   - `Purchase` — booking confirmed (with value)
   - `Lead` — operator application submitted
3. **Custom Conversions:**
   - "Booking Started" — URL contains /book
   - "Booking Completed" — thank you / confirmation page
4. **CAPI (Conversions API)** — recommended for iOS 14+ accuracy, wire through backend

---

## Budget Allocation (Week 1-2)

| Campaign | Daily | Weekly | Focus |
|----------|-------|--------|-------|
| Book a Pickup — Palm Beach | $8 | $56 | Primary |
| Book a Pickup — Broward | $7 | $49 | Primary |
| Retargeting | $5 | $35 | High-intent |
| **Total** | **$20** | **$140** | |

## KPIs to Track

| Metric | Target | Red Flag |
|--------|--------|----------|
| CPA (cost per booking) | < $15 | > $25 |
| CTR | > 1.5% | < 0.8% |
| CPM | $8-15 | > $25 |
| ROAS | > 3x | < 1.5x |
| Frequency | < 3 | > 5 |

---

## Launch Checklist

- [ ] Verify Meta Pixel installed on goumuve.com
- [ ] Create custom audiences (website visitors, booking started)
- [ ] Upload customer email list for lookalike audience (optional)
- [ ] Create 5 ad creatives (images + copy above)
- [ ] Set up conversion tracking events
- [ ] Launch Campaign 1 with $20/day
- [ ] Wait 3-5 days for learning phase
- [ ] Review performance, kill underperformers
- [ ] Launch retargeting campaign after 500+ pixel fires
- [ ] Scale winning ad sets by 20%/day

---

## Scaling Plan (Week 3+)

1. If CPA < $15: Increase daily budget by 20% every 3 days
2. Create Lookalike Audience from converters (1-3%)
3. Test new creatives every 2 weeks
4. Add Miami-Dade ad set once Palm Beach + Broward are profitable
5. Target: $50/day by month 2, $100/day by month 3
