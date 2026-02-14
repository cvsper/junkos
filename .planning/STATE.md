# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.
**Current focus:** Phase 2 - Pricing & Booking

## Current Position

Phase: 2 of 7 (Pricing & Booking)
Plan: 1 of 5
Status: In progress
Last activity: 2026-02-14 — Plan 02-01 complete (booking data model + wizard foundation)

Progress: [██░░░░░░░░] 18%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 16 minutes
- Total execution time: ~64 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | ~40 min | ~13 min |
| 2 | 1 | ~24 min | ~24 min |

**Recent Trend:**
- 02-01: 24 minutes (2 tasks, data model refactor + wizard foundation + HomeView)
- 01-03: 5 minutes (2 tasks, onboarding + Apple-only sign-in UI)
- 01-02: 15 minutes (2 tasks, driver auth + onboarding)
- 01-01: 20 minutes (2 tasks, customer auth + Keychain migration + nonce validation)

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

**From Phase 2 (in progress):**
- 5-step wizard flow: Service → Address → Photos → Schedule → Review (data dependency order)
- Tappable progress dots enable free navigation to completed steps
- Running price estimate bar sticky at bottom with expandable line-item breakdown
- Temporary legacy properties in BookingData for backward compatibility during incremental refactor

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed 02-01-PLAN.md (booking data model + wizard foundation)
Resume file: None
