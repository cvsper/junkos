# Requirements: Umuve iOS to TestFlight

**Defined:** 2026-02-13
**Core Value:** A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.

## v1 Requirements

Requirements for TestFlight release. Each maps to roadmap phases.

### Authentication

- [ ] **AUTH-01**: Customer app migrates JWT storage from UserDefaults to Keychain for security
- [ ] **AUTH-02**: Both apps validate Apple Sign In token with backend (nonce handling)

### Payments (Customer)

- [ ] **PAY-01**: Customer can pay for a booking via Stripe payment sheet
- [ ] **PAY-02**: Customer sees price breakdown before confirming payment
- [ ] **PAY-03**: Payment is held in escrow until job completion (Stripe Connect)

### Payments (Driver)

- [ ] **PAY-04**: Driver receives 80% of job price upon completion (Stripe Connect transfer)
- [ ] **PAY-05**: Driver can view earnings summary (today, this week, total)
- [ ] **PAY-06**: Driver payout settings screen shows Stripe Connect onboarding status

### Pricing Engine

- [ ] **PRICE-01**: Backend calculates price: Base Fee + Distance (MapKit) + Service Multiplier
- [ ] **PRICE-02**: Junk removal priced by volume tier (1/4, 1/2, 3/4, full truck)
- [ ] **PRICE-03**: Auto transport priced by distance with surcharges (non-running vehicle, enclosed trailer)
- [ ] **PRICE-04**: Customer sees calculated price before payment on confirmation screen

### Booking Flow (Customer)

- [ ] **BOOK-01**: Customer can select service type (Junk Removal or Auto Transport)
- [ ] **BOOK-02**: Customer photo upload sends to backend (multipart upload to S3)
- [ ] **BOOK-03**: Customer address entry uses MapKit autocomplete with distance calculation
- [ ] **BOOK-04**: Backend creates job with calculated price and assigns to dispatch queue

### Dispatch

- [ ] **DISP-01**: Available drivers receive push notification for new jobs in their area
- [ ] **DISP-02**: Driver can accept a job (first-come-first-serve)
- [ ] **DISP-03**: Job is removed from feed once accepted by a driver
- [ ] **DISP-04**: Customer receives push notification when driver is assigned

### Volume Adjustment

- [ ] **VOL-01**: Driver can input actual volume on arrival if different from estimate
- [ ] **VOL-02**: Customer receives push notification with new price for approval
- [ ] **VOL-03**: Customer can approve new price (job continues at updated price)
- [ ] **VOL-04**: Customer can decline new price (job cancelled, customer charged trip fee)
- [ ] **VOL-05**: Backend recalculates price based on driver's volume input

### Real-Time Tracking

- [ ] **TRACK-01**: Customer sees driver location on map when job is en_route
- [ ] **TRACK-02**: Customer receives push notifications for each job status change
- [ ] **TRACK-03**: Driver location streams to backend via Socket.IO when on active job

### TestFlight Readiness

- [ ] **TF-01**: Both apps compile and run on physical device without crashes
- [ ] **TF-02**: Both apps pass App Store Connect upload validation
- [ ] **TF-03**: App Store screenshots and descriptions prepared
- [ ] **TF-04**: Both apps tested end-to-end with production backend URL

## v2 Requirements

Deferred to post-TestFlight. Tracked but not in current roadmap.

### Dispatch Enhancements

- **DISP-V2-01**: Reverse auction dispatch (post job at max price, drivers bid down)
- **DISP-V2-02**: Driver bidding UI with countdown timer
- **DISP-V2-03**: Auto-fallback from auction to instant assign after timeout

### Social & Trust

- **SOCIAL-01**: Post-job rating (customer rates driver)
- **SOCIAL-02**: Post-job rating (driver rates customer)
- **SOCIAL-03**: Favorite drivers (customer can prefer specific drivers)

### Driver Enhancements

- **DRV-V2-01**: Availability schedule (set recurring hours)
- **DRV-V2-02**: Detailed earnings breakdown with graphs
- **DRV-V2-03**: Tipping support from customer

### Notifications

- **NOTF-V2-01**: Email notifications for booking confirmations
- **NOTF-V2-02**: SMS notifications via Twilio

## Out of Scope

| Feature | Reason |
|---------|--------|
| In-app chat | Phone call suffices for v1; high complexity |
| Android app | iOS-only for TestFlight milestone |
| Web platform changes | Existing web admin is sufficient |
| Driver onboarding verification | Manual admin approval for v1 |
| AI photo volume detection | Requires ML model training; use manual estimates |
| Subscription pricing | Infrequent use; per-job pricing only |
| Operator native UI | Web redirect is sufficient for v1 |
| Customer-to-driver ratings in-app | Defer to v2; focus on core flow |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Pending |
| AUTH-02 | Phase 1 | Pending |
| PRICE-01 | Phase 2 | Pending |
| PRICE-02 | Phase 2 | Pending |
| PRICE-03 | Phase 2 | Pending |
| PRICE-04 | Phase 2 | Pending |
| BOOK-01 | Phase 2 | Pending |
| BOOK-02 | Phase 2 | Pending |
| BOOK-03 | Phase 2 | Pending |
| BOOK-04 | Phase 2 | Pending |
| PAY-01 | Phase 3 | Pending |
| PAY-02 | Phase 3 | Pending |
| PAY-03 | Phase 3 | Pending |
| PAY-04 | Phase 3 | Pending |
| PAY-05 | Phase 3 | Pending |
| PAY-06 | Phase 3 | Pending |
| DISP-01 | Phase 4 | Pending |
| DISP-02 | Phase 4 | Pending |
| DISP-03 | Phase 4 | Pending |
| DISP-04 | Phase 4 | Pending |
| VOL-01 | Phase 5 | Pending |
| VOL-02 | Phase 5 | Pending |
| VOL-03 | Phase 5 | Pending |
| VOL-04 | Phase 5 | Pending |
| VOL-05 | Phase 5 | Pending |
| TRACK-01 | Phase 6 | Pending |
| TRACK-02 | Phase 6 | Pending |
| TRACK-03 | Phase 6 | Pending |
| TF-01 | Phase 7 | Pending |
| TF-02 | Phase 7 | Pending |
| TF-03 | Phase 7 | Pending |
| TF-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0

---
*Requirements defined: 2026-02-13*
*Last updated: 2026-02-13 after roadmap creation*
