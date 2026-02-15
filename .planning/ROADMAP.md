# Roadmap: Umuve iOS Apps to TestFlight

## Overview

This roadmap transforms two partially-built iOS apps (customer and driver) into TestFlight-ready applications with complete end-to-end booking, dispatch, payment, and tracking flows. Starting with secure authentication foundations, we build upward through pricing, payments, dispatch, volume adjustments, and real-time tracking, culminating in polished TestFlight builds validated against production workflows.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Authentication** - Secure auth and networking infrastructure
- [x] **Phase 2: Pricing & Booking** - Customer can see pricing and create bookings
- [x] **Phase 3: Payments Integration** - Stripe payments with escrow and driver payouts
- [x] **Phase 4: Dispatch System** - Driver assignment and job acceptance
- [x] **Phase 5: Volume Adjustment** - On-site price recalculation with customer approval
- [x] **Phase 6: Real-Time Tracking** - Live GPS tracking and status updates
- [x] **Phase 7: TestFlight Preparation** - Validation, testing, and App Store Connect readiness

## Phase Details

### Phase 1: Foundation & Authentication
**Goal**: Both apps have secure authentication with Apple Sign In and JWT token management via Keychain
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-02
**Success Criteria** (what must be TRUE):
  1. Customer app stores JWT tokens in Keychain (migrated from UserDefaults)
  2. Both apps complete Apple Sign In flow with backend nonce validation
  3. User remains authenticated across app restarts without re-login
  4. Auth token securely attached to all API requests
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Customer app Keychain migration, AuthenticationManager rewrite, backend nonce validation
- [x] 01-02-PLAN.md — Driver app nonce handling, onboarding screens, Apple-only auth UI
- [x] 01-03-PLAN.md — Customer app onboarding screens, Apple-only sign-in, app entry point rewiring

### Phase 2: Pricing & Booking
**Goal**: Customer can select service, see calculated pricing, and create a booking with photo upload
**Depends on**: Phase 1
**Requirements**: PRICE-01, PRICE-02, PRICE-03, PRICE-04, BOOK-01, BOOK-02, BOOK-03, BOOK-04
**Success Criteria** (what must be TRUE):
  1. Customer can choose between Junk Removal and Auto Transport services
  2. Customer can upload photos that reach backend (multipart upload to S3)
  3. Customer enters address via MapKit autocomplete with distance calculation
  4. Customer sees price breakdown (Base Fee + Distance + Service Multiplier) before booking
  5. Backend creates job with calculated price after customer confirms
**Plans**: 5 plans

Plans:
- [x] 02-01-PLAN.md — Data model refactoring + booking wizard container with progress indicator
- [x] 02-02-PLAN.md — Service type selection (Junk Removal / Auto Transport) with truck fill selector and vehicle info
- [x] 02-03-PLAN.md — Address entry with MapKit autocomplete, mini-map preview, and distance calculation
- [x] 02-04-PLAN.md — Photo upload + schedule adaptation for wizard, pricing API integration, running price bar
- [x] 02-05-PLAN.md — Review & confirmation screen, photo upload to backend, job creation API

### Phase 3: Payments Integration
**Goal**: Customer pays upfront via Stripe (held in escrow), driver receives 80% payout on completion
**Depends on**: Phase 2
**Requirements**: PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-06
**Success Criteria** (what must be TRUE):
  1. Customer completes payment via Stripe payment sheet before job confirmation
  2. Customer sees price breakdown one final time before payment
  3. Payment is held in escrow (not released to driver until job completes)
  4. Driver receives 80% of job price when job is marked complete
  5. Driver can view earnings summary showing today, this week, and total earnings
  6. Driver payout settings screen displays Stripe Connect onboarding status
**Plans**: 4 plans

Plans:
- [x] 03-01-PLAN.md — Stripe Payment Sheet integration in customer booking review (Apple Pay + card entry)
- [x] 03-02-PLAN.md — Backend Stripe Connect endpoints, earnings history API, webhook enhancements
- [x] 03-03-PLAN.md — Driver mandatory Stripe Connect onboarding + payout settings with status badge
- [x] 03-04-PLAN.md — Driver earnings dashboard with API integration, date filters, payout status badges

### Phase 4: Dispatch System
**Goal**: Available drivers receive job notifications, can accept jobs, and job is removed from feed once claimed
**Depends on**: Phase 3
**Requirements**: DISP-01, DISP-02, DISP-03, DISP-04
**Success Criteria** (what must be TRUE):
  1. Drivers with availability toggled "online" receive push notifications for new jobs in their area
  2. Driver can accept a job from notification or in-app feed (first-come-first-serve)
  3. Once a job is accepted, it disappears from other drivers' feeds
  4. Customer receives push notification when their job is assigned to a driver
**Plans**: 4 plans

Plans:
- [x] 04-01-PLAN.md — Backend dispatch pipeline: APNs push + Socket.IO to drivers on job creation, customer push on acceptance, broadcast job removal to all drivers
- [x] 04-02-PLAN.md — Driver app real-time feed: Socket.IO job:accepted listener, feed removal, new job insertion
- [x] 04-03-PLAN.md — Customer app notifications: driver assignment push handling, booking status display
- [x] 04-04-PLAN.md — End-to-end verification checkpoint for all four DISP requirements

### Phase 5: Volume Adjustment
**Goal**: Driver can recalculate price on-site if actual volume differs from estimate, customer approves or declines
**Depends on**: Phase 4
**Requirements**: VOL-01, VOL-02, VOL-03, VOL-04, VOL-05
**Success Criteria** (what must be TRUE):
  1. Driver can input actual volume on arrival when estimate is incorrect
  2. Customer receives push notification with new price for approval
  3. Customer can approve new price (job continues at updated price)
  4. Customer can decline new price (job cancelled, customer charged trip fee)
  5. Backend recalculates price using driver's volume input
**Plans**: 4 plans

Plans:
- [x] 05-01-PLAN.md — Backend volume adjustment endpoints, Job model fields, APNs category support, Stripe PaymentIntent updates
- [x] 05-02-PLAN.md — Driver app volume input UI, price preview, API integration, Socket.IO approval/decline listener
- [x] 05-03-PLAN.md — Customer app actionable push notification (approve/decline), in-app fallback banner, API methods
- [x] 05-04-PLAN.md — End-to-end verification of all 5 VOL requirements across backend + both iOS apps

### Phase 6: Real-Time Tracking
**Goal**: Customer sees driver location on map when job is active, receives push notifications for status changes
**Depends on**: Phase 5
**Requirements**: TRACK-01, TRACK-02, TRACK-03
**Success Criteria** (what must be TRUE):
  1. Customer app displays driver location on map when job status is en_route
  2. Customer receives push notifications for each job status transition
  3. Driver location streams to backend via Socket.IO during active jobs
**Plans**: 3 plans

Plans:
- [x] 06-01-PLAN.md — Driver location streaming + backend push notifications for all status transitions
- [x] 06-02-PLAN.md — Customer Socket.IO manager + tracking map view + notification categories
- [x] 06-03-PLAN.md — Wire tracking into booking cards + end-to-end verification

### Phase 7: TestFlight Preparation
**Goal**: Both apps compile, pass validation, and complete end-to-end testing on physical devices
**Depends on**: Phase 6
**Requirements**: TF-01, TF-02, TF-03, TF-04
**Success Criteria** (what must be TRUE):
  1. Both apps compile and run on physical device without crashes
  2. Both apps successfully upload to App Store Connect and pass validation
  3. App Store screenshots, descriptions, and privacy details prepared
  4. Both apps tested end-to-end (customer books → driver accepts → completes → payment) using production backend URL
**Plans**: 3 plans

Plans:
- [x] 07-01-PLAN.md — Build validation, entitlements fix, Release compilation
- [x] 07-02-PLAN.md — Privacy policy page and App Store Connect metadata
- [x] 07-03-PLAN.md — Production backend testing, physical device verification, App Store Connect upload

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Authentication | 3/3 | Complete | 2026-02-14 |
| 2. Pricing & Booking | 5/5 | Complete | 2026-02-14 |
| 3. Payments Integration | 4/4 | Complete | 2026-02-14 |
| 4. Dispatch System | 4/4 | Complete | 2026-02-14 |
| 5. Volume Adjustment | 4/4 | Complete | 2026-02-14 |
| 6. Real-Time Tracking | 3/3 | Complete | 2026-02-14 |
| 7. TestFlight Preparation | 3/3 | Complete | 2026-02-15 |

---
*Roadmap created: 2026-02-13*
*Last updated: 2026-02-15*
