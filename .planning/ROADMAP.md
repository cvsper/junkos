# Roadmap: Umuve iOS Apps to TestFlight

## Overview

This roadmap transforms two partially-built iOS apps (customer and driver) into TestFlight-ready applications with complete end-to-end booking, dispatch, payment, and tracking flows. Starting with secure authentication foundations, we build upward through pricing, payments, dispatch, volume adjustments, and real-time tracking, culminating in polished TestFlight builds validated against production workflows.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Authentication** - Secure auth and networking infrastructure
- [ ] **Phase 2: Pricing & Booking** - Customer can see pricing and create bookings
- [ ] **Phase 3: Payments Integration** - Stripe payments with escrow and driver payouts
- [ ] **Phase 4: Dispatch System** - Driver assignment and job acceptance
- [ ] **Phase 5: Volume Adjustment** - On-site price recalculation with customer approval
- [ ] **Phase 6: Real-Time Tracking** - Live GPS tracking and status updates
- [ ] **Phase 7: TestFlight Preparation** - Validation, testing, and App Store Connect readiness

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
- [ ] 01-01-PLAN.md — Customer app Keychain migration, AuthenticationManager rewrite, backend nonce validation
- [ ] 01-02-PLAN.md — Driver app nonce handling, onboarding screens, Apple-only auth UI
- [ ] 01-03-PLAN.md — Customer app onboarding screens, Apple-only sign-in, app entry point rewiring

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
**Plans**: TBD

Plans:
- TBD (pending phase planning)

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
**Plans**: TBD

Plans:
- TBD (pending phase planning)

### Phase 4: Dispatch System
**Goal**: Available drivers receive job notifications, can accept jobs, and job is removed from feed once claimed
**Depends on**: Phase 3
**Requirements**: DISP-01, DISP-02, DISP-03, DISP-04
**Success Criteria** (what must be TRUE):
  1. Drivers with availability toggled "online" receive push notifications for new jobs in their area
  2. Driver can accept a job from notification or in-app feed (first-come-first-serve)
  3. Once a job is accepted, it disappears from other drivers' feeds
  4. Customer receives push notification when their job is assigned to a driver
**Plans**: TBD

Plans:
- TBD (pending phase planning)

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
**Plans**: TBD

Plans:
- TBD (pending phase planning)

### Phase 6: Real-Time Tracking
**Goal**: Customer sees driver location on map when job is active, receives push notifications for status changes
**Depends on**: Phase 5
**Requirements**: TRACK-01, TRACK-02, TRACK-03
**Success Criteria** (what must be TRUE):
  1. Customer app displays driver location on map when job status is en_route
  2. Customer receives push notifications for each job status transition
  3. Driver location streams to backend via Socket.IO during active jobs
**Plans**: TBD

Plans:
- TBD (pending phase planning)

### Phase 7: TestFlight Preparation
**Goal**: Both apps compile, pass validation, and complete end-to-end testing on physical devices
**Depends on**: Phase 6
**Requirements**: TF-01, TF-02, TF-03, TF-04
**Success Criteria** (what must be TRUE):
  1. Both apps compile and run on physical device without crashes
  2. Both apps successfully upload to App Store Connect and pass validation
  3. App Store screenshots, descriptions, and privacy details prepared
  4. Both apps tested end-to-end (customer books → driver accepts → completes → payment) using production backend URL
**Plans**: TBD

Plans:
- TBD (pending phase planning)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Authentication | 0/3 | Planning complete | - |
| 2. Pricing & Booking | 0/TBD | Not started | - |
| 3. Payments Integration | 0/TBD | Not started | - |
| 4. Dispatch System | 0/TBD | Not started | - |
| 5. Volume Adjustment | 0/TBD | Not started | - |
| 6. Real-Time Tracking | 0/TBD | Not started | - |
| 7. TestFlight Preparation | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-13*
*Last updated: 2026-02-13*
