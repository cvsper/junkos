# Umuve SEO Expansion Plan — Competitor Parity + Beyond

## Current State: 55 pages live
- 42 city pages (`/junk-removal/{city}-fl`)
- 10 service pages (`/services/{service}`)
- 3 comparison pages (`/vs/{competitor}`)

## Competitor Analysis

### 1-800-GOT-JUNK (1,000+ pages)
**Page types we DON'T have:**
1. **Service × City combo pages** — e.g., `/junk-removal/boca-raton-fl/furniture-removal` (14 service types × 42 cities = 588 pages)
2. **Commercial service pages** — retail, construction debris, hospital/school, office cleanout
3. **"What We Take" hub pages** — furniture, appliances, electronics, dumpster alternative, residential junk
4. **How-to/disposal guide blog posts** — "how to dispose of [item]", "how to remove [item]"
5. **Neighborhood pages** — sub-city targeting (e.g., Boca Raton → Boca West, Town Center, Mizner Park)
6. **Recycling-specific pages** — electronics recycling, metal recycling, glass recycling, computer recycling, TV recycling

### College Hunks (750+ pages)
**Page types we DON'T have:**
1. **Moving service pages** — they combine junk + moving (we're junk-only, skip these)
2. **State-level hub pages** — `/junk-removal/florida/` (aggregates all cities)
3. **Massive city coverage** — 750+ cities nationwide (we only need South FL)

---

## Build Plan — Priority Order

### Phase 1: Service × City Combo Pages (HIGH IMPACT — 588 pages)
Every city page gets a sub-page for each service type.

**14 service types:**
1. furniture-removal
2. mattress-disposal
3. appliance-removal
4. electronics-recycling
5. couch-removal
6. refrigerator-disposal
7. hot-tub-removal
8. tv-recycling
9. construction-debris-removal
10. yard-waste-removal
11. garage-cleanout
12. estate-cleanout
13. office-cleanout
14. dumpster-alternative

**URL pattern:** `/junk-removal/{city}-fl/{service}`
**Example:** `/junk-removal/boca-raton-fl/furniture-removal`

**Why this matters:** These are the exact long-tail keywords people search: "furniture removal boca raton", "appliance removal fort lauderdale". GOT-JUNK dominates these SERPs because they have dedicated pages. We don't.

**Estimated pages:** 42 cities × 14 services = **588 pages**

### Phase 2: How-To / Disposal Guide Pages (MEDIUM IMPACT — 30+ pages)
Blog-style content targeting informational queries that lead to bookings.

**Pages to build:**
- how-to-dispose-of-a-mattress
- how-to-dispose-of-a-refrigerator
- how-to-dispose-of-electronics
- how-to-dispose-of-paint
- how-to-dispose-of-a-couch
- how-to-dispose-of-appliances
- how-to-dispose-of-a-tv
- how-to-dispose-of-tires
- how-to-dispose-of-a-hot-tub
- how-to-dispose-of-a-washer-dryer
- how-to-dispose-of-concrete
- how-to-dispose-of-drywall
- how-to-dispose-of-a-dishwasher
- how-to-dispose-of-a-dehumidifier
- how-to-dispose-of-a-stove-oven
- how-to-remove-a-toilet
- how-to-remove-drywall
- how-to-remove-a-kitchen-sink
- how-to-take-apart-a-bed-frame
- how-to-take-apart-a-couch
- declutter-before-moving
- declutter-for-spring-cleaning
- what-to-do-with-old-furniture
- garage-cleanout-guide
- estate-cleanout-checklist
- move-out-cleaning-checklist
- renovation-debris-disposal-guide
- hoarder-cleanout-guide
- storage-unit-cleanout-guide
- downsizing-tips

**URL pattern:** `/guides/{slug}`

### Phase 3: Neighborhood Sub-Pages (MEDIUM IMPACT — 100+ pages)
Target specific neighborhoods within each city for hyper-local SEO.

**Example for Boca Raton:**
- /junk-removal/boca-raton-fl/boca-west
- /junk-removal/boca-raton-fl/mizner-park
- /junk-removal/boca-raton-fl/broken-sound
- /junk-removal/boca-raton-fl/town-center

**Example for Fort Lauderdale:**
- /junk-removal/fort-lauderdale-fl/las-olas
- /junk-removal/fort-lauderdale-fl/victoria-park
- /junk-removal/fort-lauderdale-fl/wilton-manors
- /junk-removal/fort-lauderdale-fl/oakland-park

**Estimated:** 42 cities × ~3 neighborhoods each = **~126 pages**

### Phase 4: Commercial Service Pages (MEDIUM IMPACT — 8+ pages)
Dedicated pages for commercial/B2B junk removal.

**Pages:**
- /commercial (hub)
- /commercial/office-cleanout
- /commercial/retail-store-cleanout
- /commercial/construction-debris
- /commercial/restaurant-cleanout
- /commercial/warehouse-cleanout
- /commercial/property-management
- /commercial/hoa-services

### Phase 5: Additional Comparison Pages (LOW IMPACT — 5+ pages)
We have 3, competitors have more.

**Add:**
- /vs/college-hunks
- /vs/trash-butler
- /vs/bagster
- /vs/junk-removal-near-me (general comparison)
- /vs/diy-junk-removal (cost comparison)

### Phase 6: Hub / Pillar Pages (LOW IMPACT — 5 pages)
Top-level pages that link to all sub-pages.

**Pages:**
- /services (hub linking to all 10+ service pages)
- /locations (hub linking to all 42+ city pages)
- /guides (hub linking to all how-to pages)
- /commercial (hub linking to commercial sub-pages)
- /pricing (transparent pricing page — competitor advantage)

---

## Total New Pages to Build

| Phase | Pages | Priority | SEO Impact |
|-------|-------|----------|------------|
| 1. Service × City combos | 588 | HIGH | Long-tail dominance |
| 2. How-to guides | 30 | HIGH | Informational traffic → bookings |
| 3. Neighborhood pages | 126 | MEDIUM | Hyper-local targeting |
| 4. Commercial pages | 8 | MEDIUM | B2B revenue channel |
| 5. More comparisons | 5 | LOW | Brand positioning |
| 6. Hub pages | 5 | LOW | Internal linking |
| **Total** | **762** | | |

## Implementation Notes

- All pages should use the existing SEO generator framework (`seo-generator/`)
- Every page needs: Meta Pixel, GA4, schema markup (LocalBusiness+Service+FAQ+Breadcrumb)
- Every page needs sticky CTA bar, internal linking to related city/service pages
- Sitemap must be updated after each phase
- Phase 1 is programmatic — one template, data-driven generation
- Phase 2 requires unique content per guide (can use AI but needs quality review)
- Deploy in batches: 50-100 pages at a time to avoid Google sandbox

## Execution

**Recommended:** Start a fresh session for Phase 1 (588 service×city pages).
The SEO generator already handles city pages — extend it with a service×city template.
