# Umuve - iOS Apps to TestFlight

## What This Is

Umuve is a two-sided marketplace for junk removal and auto transport. Customers book hauling services through the Umuve iOS app (browse services, upload photos, get a quote, schedule pickup, pay via Stripe). Drivers accept and complete jobs through the Umuve Pro iOS app. The platform takes a 20% commission on every completed transaction.

## Core Value

A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- Flask REST API backend with JWT authentication
- SQLAlchemy database models (User, Job, Contractor, Payment, Address)
- Role-based access control (customer, driver, admin, operator)
- Real-time WebSocket updates via Socket.IO
- Stripe payment integration (backend)
- Push notification infrastructure (APNs configured in backend)
- Next.js admin/operator/customer web platform
- Landing page deployed to Vercel
- iOS customer app shell (JunkOS-Clean / Umuve) — partially built
- iOS driver app shell (JunkOS-Driver / Umuve Pro) — partially built
- Job status progression (pending → confirmed → delegating → assigned → en_route → arrived → in_progress → completed/cancelled)

### Active

<!-- Current scope: Get both iOS apps TestFlight-ready with full end-to-end flow. -->

**Customer App (Umuve):**
- [ ] Apple Sign In authentication
- [ ] Service selection (Junk Removal vs Auto Transport)
- [ ] Photo upload for junk volume estimation
- [ ] Address entry with MapKit autocomplete
- [ ] Pricing display: Base Fee + Distance (MapKit) + Service Multiplier
- [ ] Volume-based pricing for junk removal (1/4, 1/2, 3/4, full truck)
- [ ] Distance-based pricing for auto transport with surcharges (non-running, enclosed)
- [ ] Schedule pickup date/time selection
- [ ] Stripe payment (customer pays upfront, held in escrow)
- [ ] Real-time job tracking with driver location on map
- [ ] Push notification for job status updates
- [ ] Push notification for volume adjustment approval (approve new price or cancel + trip fee)
- [ ] Job history and status viewing

**Driver App (Umuve Pro):**
- [ ] Apple Sign In authentication
- [ ] Availability toggle (online/offline)
- [ ] Incoming job notifications with job details
- [ ] Accept / reject / bid on jobs (reverse auction + instant book)
- [ ] Navigation to customer via Apple Maps
- [ ] Volume adjustment input (driver arrives, actual volume differs from estimate)
- [ ] Photo proof of completion
- [ ] Job completion flow
- [ ] Earnings summary (80% of job price)

**Backend (supporting iOS flows):**
- [ ] Pricing engine endpoint: Base Fee + Distance + Service Multiplier
- [ ] Reverse auction / instant book dispatch system
- [ ] Volume adjustment workflow (driver submits → customer approves/declines → price update or cancel + trip fee)
- [ ] Stripe Connect split payments (20% platform / 80% driver escrow → release on completion)
- [ ] Apple Sign In token verification

### Out of Scope

- Web platform improvements — focus is iOS only for this milestone
- React Native mobile app — native Swift iOS is the path forward
- Email/SMS notifications — push notifications only for iOS
- Admin dashboard changes — existing web admin is sufficient
- Customer-portal (Svelte/React) — web booking not in scope
- Social login beyond Apple (Google, Facebook) — Apple Sign In only
- In-app chat between customer and driver — phone call suffices for v1
- Driver onboarding / verification flow — manual approval for v1
- Ratings and reviews — defer to post-TestFlight

## Context

- Two iOS Xcode projects exist: `JunkOS-Clean/` (customer) and `JunkOS-Driver/` (driver) — directory names intentionally NOT renamed from rebrand
- Backend is deployed on Render at `junkos-backend.onrender.com`
- Backend already has Stripe, Twilio, APNs, and S3 integrations
- Push notifications may already be partially configured — needs verification
- iOS apps use SwiftUI with MVVM pattern
- Bundle IDs: `com.goumuve.app` (customer), `com.goumuve.pro` (driver)
- Brand: Bold red (#DC2626), Outfit + DM Sans fonts, "Hauling made simple." tagline
- Existing web platform has booking flow, job tracking, and admin — iOS apps should match these capabilities

## Constraints

- **Maps**: Apple Maps / MapKit only — no Google Maps or Mapbox
- **Auth**: Apple Sign In required (App Store requirement when offering social login)
- **Payments**: Stripe Connect for marketplace split payments — no alternatives
- **Platform**: iOS only (no Android) — SwiftUI, minimum iOS 14+
- **Backend URL**: `https://junkos-backend.onrender.com` (not renamed)
- **Xcode projects**: Do NOT rename project files or directories — causes cascading build failures
- **TestFlight**: Must compile, run on device, and pass App Store Connect upload validation

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Apple Sign In only (no email/password on iOS) | App Store requires it when offering social login; simplest auth UX on iOS | — Pending |
| Apple Maps / MapKit for distance + navigation | Free, native iOS integration, no API key costs | — Pending |
| Reverse auction + instant book dispatch | Market-driven pricing without manual dispatching; user described this model | — Pending |
| 20% platform commission with Stripe Connect | Standard marketplace take rate; Stripe handles split payments and escrow | — Pending |
| Volume adjustment workflow with customer approval | Keeps pricing automated; protects customer from surprise charges | — Pending |
| Trip fee on customer decline after driver arrives | Compensates driver for wasted time; prevents abuse of volume adjustments | — Pending |

---
*Last updated: 2026-02-13 after initialization*
