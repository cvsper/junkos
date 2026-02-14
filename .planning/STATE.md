# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.
**Current focus:** Phase 1 - Foundation & Authentication

## Current Position

Phase: 1 of 7 (Foundation & Authentication)
Plan: 4 of TBD
Status: In progress
Last activity: 2026-02-14 — Completed plan 01-03 (customer onboarding + Apple-only sign-in UI)

Progress: [███░░░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 14 minutes
- Total execution time: 0.92 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 4 | 55 min | 14 min |

**Recent Trend:**
- 01-03: 5 minutes (2 tasks, onboarding + Apple-only sign-in UI)
- 01-01: 20 minutes (2 tasks, customer auth + Keychain migration + nonce validation)
- 01-02: 15 minutes (2 tasks, driver auth + onboarding)

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

**From 01-03:**
- Use PageTabViewStyle for native iOS swipeable onboarding with dots indicator
- Remove OnboardingManager class — use @AppStorage directly for simplicity
- Deprecate EnhancedWelcomeView instead of deleting to preserve Xcode project references
- Use NWPathMonitor for offline detection with animated banner overlay
- Add sign-out confirmation alert to prevent accidental logouts

**From 01-02:**
- Remove email/password auth entirely from driver app (Apple Sign In only)
- Show onboarding before auth screen on first launch
- Retry Apple Sign In up to 3 times with 1-second delays
- Refresh JWT when expiring within 24 hours

**From 01-01:**
- Use ObservableObject instead of @Observable for iOS 16 compatibility
- Cache Apple public keys for 24 hours to reduce API calls
- Support legacy userIdentifier flow for backward compatibility during transition
- 7-day grace period for token refresh to handle offline scenarios

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed 01-03-PLAN.md — customer onboarding + Apple-only sign-in UI
Resume file: None
