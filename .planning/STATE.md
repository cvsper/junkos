# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.
**Current focus:** Phase 1 - Foundation & Authentication

## Current Position

Phase: 1 of 7 (Foundation & Authentication)
Plan: 2 of TBD
Status: In progress
Last activity: 2026-02-14 — Completed plan 01-02 (driver auth hardening + onboarding)

Progress: [██░░░░░░░░] 20%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 15 minutes
- Total execution time: 0.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | 30 min | 15 min |

**Recent Trend:**
- 01-02: 15 minutes (2 tasks, driver auth + onboarding)
- 01-01: 15 minutes (customer auth hardening)

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

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed 01-02-PLAN.md — driver auth hardening, onboarding, token refresh
Resume file: None
