# Phase 2: Pricing & Booking - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Customer app gets a complete booking flow: select service (Junk Removal or Auto Transport), upload photos, enter address(es), see calculated pricing, pick a schedule, and confirm. Backend creates the job with calculated price. No payment in this phase — that's Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Booking flow structure
- Step-by-step wizard with one screen per step and progress indicator
- Free navigation: back button + tappable progress dots to jump to any completed step
- Running price estimate updates as the customer fills in steps (not just at review)
- Step order is Claude's discretion based on data dependencies

### Service selection
- Two large full-width tappable cards with icon, title, and brief description
- Junk Removal card and Auto Transport card — tap to select, highlighted state
- For Junk Removal: visual truck fill selector with illustration showing 1/4, 1/2, 3/4, full truck levels
- For Auto Transport: additional fields for vehicle info + surcharges (non-running, enclosed) per PROJECT.md

### Photo upload
- Camera + photo gallery as sources
- Maximum 10 photos per booking
- Whether photos are required or optional is Claude's discretion (consider: photos help accuracy, but requiring them adds friction)

### Address entry
- Junk Removal: pickup address only (driver handles disposal)
- Auto Transport: pickup + dropoff addresses
- Address entry UX is Claude's discretion (text field with MapKit autocomplete, map pin, or hybrid)
- Show mini-map preview after address selection

### Pricing display
- Running estimate shown as customer progresses through steps
- Summary with expandable detail: total shown prominently, tap to expand for line items (Base Fee, Distance Fee, Service Multiplier)
- Price updates when relevant inputs change (service type, address, volume)

### Review & confirm screen
- Full summary card showing everything: service type, address(es), photo thumbnails, scheduled date/time, price with expandable breakdown
- Single "Confirm Booking" button at bottom
- This is the last step before job creation (payment comes in Phase 3)

### Claude's Discretion
- Exact step order in the wizard (optimize for data dependencies — e.g., address before pricing calc)
- Whether photos are required (at least 1) or optional with encouragement
- Address entry UX (text autocomplete vs map pin vs hybrid)
- Schedule picker design (date + time selection)
- Progress indicator style (dots, numbered steps, progress bar)
- Loading and error states throughout the flow
- Photo upload UI (grid preview, reorder, delete)

</decisions>

<specifics>
## Specific Ideas

- Visual truck fill selector should feel intuitive — illustration of a truck that fills up as you tap levels, not just text options
- Service selection cards should be prominent and clear — this is the first decision the customer makes
- Running price estimate creates transparency and builds trust with the customer
- Review screen should feel like a clean order summary — everything visible at a glance before committing

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-pricing-booking*
*Context gathered: 2026-02-14*
