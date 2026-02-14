# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.
**Current focus:** Phase 1 - Foundation & Authentication

## Current Position

Phase: 1 of 7 (Foundation & Authentication)
Plan: 3 of TBD
Status: In progress
Last activity: 2026-02-14 — Completed plan 01-01 (customer auth infrastructure with Keychain + nonce validation)

Progress: [███░░░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 17 minutes
- Total execution time: 0.83 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | 50 min | 17 min |

**Recent Trend:**
- 01-01: 20 minutes (2 tasks, customer auth + Keychain migration + nonce validation)
- 01-02: 15 minutes (2 tasks, driver auth + onboarding)
- 01-01-previous: 15 minutes (customer auth hardening)

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
Stopped at: Completed 01-01-PLAN.md — customer auth infrastructure (Keychain, Apple Sign In nonce, token refresh, authenticated API)
Resume file: None
