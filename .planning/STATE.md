# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.
**Current focus:** Phase 4 - Dispatch System

## Current Position

Phase: 4 of 7 (Dispatch System)
Plan: 0 of TBD
Status: Not started
Last activity: 2026-02-14 — Phase 3 verified and complete

Progress: [██████░░░░] 43%

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: 8.5 minutes
- Total execution time: ~102 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | ~40 min | ~13 min |
| 2 | 5 | ~54 min | ~10.8 min |
| 3 | 4 | ~6.8 min | ~1.7 min |

**Recent Trend:**
- 03-04: 2.5 minutes (2 tasks, driver earnings dashboard API integration)
- 03-03: 2.3 minutes (2 tasks, Stripe Connect onboarding + payout settings)
- 03-02: 2 minutes (2 tasks, Stripe Connect endpoints + earnings history API)
- 02-05: 5 minutes (2 tasks, review screen + job creation API)
- 02-04: 14 minutes (2 tasks, photos + schedule + pricing API integration)
- 02-03: 6 minutes (2 tasks, MapKit autocomplete address input)
- 02-02: 5 minutes (2 tasks, service type selection + wizard integration)
- 02-01: 24 minutes (2 tasks, data model refactor + wizard foundation + HomeView)
- 01-03: 5 minutes (2 tasks, onboarding + Apple-only sign-in UI)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Apple Sign In only (no email/password on iOS) — App Store requirement, simplest auth UX
- Apple Maps / MapKit for distance + navigation — Free, native iOS, no API key costs
- Reverse auction + instant book dispatch — Market-driven pricing without manual dispatching
- 20% platform commission with Stripe Connect — Standard marketplace take, handles split payments
- Volume adjustment workflow with customer approval — Automated pricing with customer protection
- Trip fee on customer decline after driver arrives — Compensates driver for wasted time

**From Phase 1 (complete):**
- Use ObservableObject instead of @Observable for iOS 16 compatibility
- Cache Apple public keys for 24 hours to reduce API calls
- Support legacy userIdentifier flow for backward compatibility during transition
- 7-day grace period for token refresh to handle offline scenarios
- Use PageTabViewStyle for native iOS swipeable onboarding with dots indicator
- Use @AppStorage directly for onboarding state (no manager class)
- Use NWPathMonitor for offline detection with animated banner overlay
- Deprecate EnhancedWelcomeView instead of deleting to preserve Xcode project references

**From Phase 2 (complete):**
- 5-step wizard flow: Service → Address → Photos → Schedule → Review (data dependency order)
- Tappable progress dots enable free navigation to completed steps
- Running price estimate bar sticky at bottom with expandable line-item breakdown (hidden on review step)
- Temporary legacy properties in BookingData for backward compatibility during incremental refactor
- Each wizard step manages its own ScrollView to avoid nesting conflicts
- Single MKLocalSearchCompleter with searchMode enum for pickup/dropoff (simpler than two completers)
- 300ms debounce for autocomplete search to balance responsiveness and API efficiency
- Max 5 autocomplete suggestions to avoid overwhelming UI on mobile
- Horizontal bar blocks for truck fill visualization (simpler than custom illustrations)
- Photos are optional but encouraged (encouragement message shown when empty)
- Volume tier maps to item quantity for backend pricing API (quarter→2, half→5, threeQuarter→10, full→16)
- Pricing API calls are best-effort with silent failure (don't block user flow)
- Price estimate refreshes automatically when wizard step changes
- Upload photos first, then create job (sequential API calls for data integrity)
- Success overlay with job ID display instead of separate confirmation screen
- Mini-maps (MapKit) in review cards for visual address confirmation
- Wizard dismisses and resets on booking completion

**From Phase 3 (complete):**
- Earnings history shows driver_payout_amount only (80% take), not full job price — drivers see their earnings, not customer price
- Account links generated fresh every request, never cached — links expire in 5 minutes
- Connect status derived from Stripe API, not stored in DB — Stripe is source of truth for onboarding state
- Connect onboarding mandatory after registration, before main app access — drivers cannot reach job feed without payout method
- Status polling on view appear and Safari dismissal — Stripe onboarding is async, need to check for completion
- [Phase 03]: 4-segment date filter (today/week/month/all-time) with period-based earnings filtering
- [Phase 03]: Payout status badge colors: pending=amber, processing=blue, paid=green

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-14
Stopped at: Phase 3 complete and verified — ready for Phase 4 planning
Resume file: None
