# Project Research Summary

**Project:** Umuve iOS Apps (Customer + Driver)
**Domain:** Two-sided marketplace for hauling/junk removal services
**Researched:** 2026-02-13
**Confidence:** HIGH

## Executive Summary

Umuve is a two-sided iOS marketplace connecting customers with drivers for hauling and junk removal services. Based on comprehensive research, the recommended approach is native SwiftUI apps targeting iOS 16+ (89.6% device coverage) with Swift 6.0, leveraging Swift Package Manager for dependencies. The architecture follows MVVM with Clean Architecture separation, using modern Swift concurrency (async/await) throughout and @Observable for state management. Core technologies include MapKit for location/routing, Stripe Connect for marketplace payments, Socket.IO for real-time dispatch, and APNs for notifications.

The product requires implementing both table stakes features (photo-based estimates, transparent pricing, real-time tracking, in-app payments, two-way ratings) and key differentiators (reverse auction dispatch, volume adjustment workflow, instant vs auction hybrid booking). The architecture must handle real-time bidding, live GPS tracking, split payments, and dual mobile apps sharing a Flask backend with Socket.IO and Stripe Connect already implemented.

Critical risks include Socket.IO background disconnections (iOS aggressively suspends WebSockets, breaking dispatch), Stripe Connect balance transfer timing failures (transfers before funds available), location battery drain (continuous GPS tracking), and Apple Sign In nonce handling production failures. Mitigation requires using APNs for critical events (not Socket.IO), tying transfers to charge IDs, implementing adaptive location accuracy, and following Apple's authentication best practices. TestFlight rejections under Guideline 2.1 are the highest risk (40% of rejections), requiring extensive physical device testing and detailed App Review Notes.

## Key Findings

### Recommended Stack

SwiftUI with MVVM architecture on iOS 16+ provides the optimal balance of modern development patterns, device coverage, and Apple platform integration. Swift 6.0 is required for App Store submissions starting April 28, 2026, making it non-negotiable. Swift Package Manager is the only viable dependency manager after CocoaPods goes read-only in December 2026.

**Core technologies:**
- **SwiftUI (iOS 16+)**: Native declarative UI framework with excellent Xcode integration, already partially implemented in both apps
- **MapKit/CoreLocation**: All required features (routing, distance, geocoding, tracking) at zero cost vs Google Maps SDK ($200/month minimum)
- **Stripe iOS SDK (25.6+)**: Official payment SDK with PaymentSheet integration, connects to existing Flask backend Stripe Connect implementation for marketplace split payments
- **Socket.IO Swift Client (16.1.1)**: Real-time job dispatch and location streaming, matches backend Flask-SocketIO v5.3.6 implementation
- **APNs + UserNotifications**: Critical event delivery (job alerts, status updates) with iOS 18 priority notifications support
- **Keychain Services**: Secure JWT token storage with hardware-backed encryption, required for PCI compliance

**Critical version requirements:**
- iOS deployment target: 16.0 (89.6% coverage)
- Xcode 16+ (required for App Store after April 28, 2026)
- Swift 6.0 (required by Xcode 16 for 2026 submissions)

**Avoid:** Firebase (duplicate systems, vendor lock-in), Google Maps (unnecessary cost), CocoaPods (deprecated Dec 2026), Redux/TCA (over-engineered), StoreKit (physical services exempt from IAP)

### Expected Features

Research identified 14 table stakes features users expect in all marketplace apps, 7 competitive differentiators for Umuve, and 6 anti-features to avoid.

**Must have (table stakes):**
- Photo-based estimation with manual admin review (industry standard from LoadUp, Curb-It)
- Transparent upfront pricing with full breakdown (Base + Distance + Service Multiplier model)
- In-app payment via Stripe Connect with split payments (customer → platform → driver minus 20% commission)
- Push notifications for job lifecycle events (iOS 18 priority notifications)
- Two-way ratings/reviews with verified purchase badges
- Job acceptance/rejection for drivers (first-come-first-serve dispatch for MVP)
- Background-checked drivers (MVR + criminal background via Persona/Authenticate)
- Navigation integration via deep links to Apple Maps/Google Maps
- Proof of service completion with before/after photos + GPS timestamp
- Driver earnings dashboard with real-time totals and weekly summaries
- Job history for customers (past bookings, costs, providers)
- Cancellation policy (48-72 hour full refund window)
- Customer support (in-app help, email, phone)
- Flexible scheduling (same-day and future booking)

**Should have (competitive differentiators):**
- Reverse auction dispatch (unique vs LoadUp/1-800-GOT-JUNK fixed pricing, drivers bid competitively)
- Volume adjustment on-site (driver recalculates invoice when estimated volume ≠ actual volume, customer approves before proceeding)
- Instant book + auction hybrid (two booking paths: "Book Now" fixed price vs "Get Bids" wait 5-10min)
- Real-time GPS tracking with Live Activities (iOS 16+ Lock Screen integration)
- Favorite/preferred drivers (repeat booking loyalty, Fresha model: first job 20% fee, repeats free)
- Tip/gratuity feature (post-job digital tipping via Stripe, Kickfin tax compliance model)
- Eco-friendly disposal tracking (driver logs disposal destination: recycled/donated/landfill)

**Defer (v2+):**
- AI-powered photo volume detection (computer vision for cubic yard estimation, defer until manual review becomes bottleneck)
- Split payment options (pay with multiple cards, adds refund complexity)
- Same-provider bundled services (auto transport + junk removal in one job)
- Price match guarantee (marketing feature, not technical)

**Anti-features to avoid:**
- Real-time chat during active job (distracts drivers while driving, liability risk)
- Subscription pricing for customers (junk removal is infrequent, would attract high-volume users and lose money)
- Automatic driver assignment without choice (drivers hate forced jobs, increases cancellations)
- Gamification badges/leaderboards (patronizing for professional drivers, focus on earnings transparency instead)

### Architecture Approach

MVVM with Clean Architecture layers using SwiftUI, separating concerns into Views (presentation), ViewModels (@Observable state), Managers (cross-cutting singletons), Services (domain operations), and Models (Codable DTOs). The architecture uses modern Swift concurrency (async/await) throughout, replacing completion handlers and combine publishers where possible.

**Major components:**
1. **APIClient (actor)** — Thread-safe networking layer with URLSession async/await, JWT token attachment, automatic error handling (200-299 success, 401 unauthorized, server errors)
2. **AuthenticationManager (@Observable singleton)** — Login/signup/Apple Sign In orchestration, Keychain token persistence, notification re-registration
3. **SocketIOManager (@Observable singleton)** — Single WebSocket connection per app lifecycle, real-time job alerts, live location streaming, automatic reconnection
4. **LocationManager (CLLocationManagerDelegate)** — Background GPS tracking with adaptive accuracy, significant-change service for battery optimization, geofencing for pickup/dropoff zones
5. **NotificationManager (UNUserNotificationCenterDelegate)** — APNs registration, push permission handling, deep link routing from notification taps
6. **PaymentService** — Stripe PaymentIntent creation via backend, Apple Pay integration with PKPaymentAuthorizationViewController, payment confirmation
7. **ViewModels** — Business logic orchestration, async service calls, @Observable state updates triggering SwiftUI re-renders

**Critical patterns:**
- Actor-based networking prevents data races (compile-time safety)
- @Observable instead of ObservableObject+@Published (iOS 17+, better performance, automatic observation)
- Keychain for JWT tokens (never UserDefaults, security requirement)
- Singleton Socket.IO with single connection (battery optimization, avoid multiple TCP connections)
- NavigationStack with enum-based deep linking (type-safe routing, centralized navigation)
- Backend-driven Stripe payments (create PaymentIntent server-side, confirm client-side for PCI compliance)

**Data flow example (job dispatch):**
```
Backend emits Socket.IO "job:new" event
→ SocketIOManager receives, updates @Observable newJobAlert property
→ JobFeedViewModel polls alert
→ SwiftUI View automatically re-renders with new job card
→ Driver taps "Accept"
→ ViewModel calls APIClient.acceptJob() async
→ Backend returns confirmation
→ View navigates to JobDetailView
```

**Anti-patterns to avoid:**
- API calls directly in SwiftUI views (violates separation of concerns, untestable)
- UserDefaults for tokens (unencrypted, security violation)
- Retain cycles in Socket.IO closures (use [weak self])
- N+1 queries fetching details for list items (backend should include necessary data)
- ObservableObject after iOS 17 (poor performance vs @Observable)
- Multiple WebSocket connections (battery drain, duplicate listeners)
- Always-on background location without user value (Apple rejection, trust issues)

### Critical Pitfalls

Research identified 12 pitfalls across critical (rewrites/rejections), moderate (UX degradation), and minor (development friction) severity levels. Top 5 require architectural decisions upfront to avoid.

1. **Socket.IO background disconnections** — iOS aggressively terminates WebSocket connections when app backgrounds or device locks. Drivers miss job offers during critical 30-60 second bidding window. Customers can't see live location. **Prevention:** Use APNs for critical events (new job, bid accepted, volume change), reserve Socket.IO for foreground-only (live chat, active tracking). Never rely on background audio/location tricks to keep sockets alive (App Store violation).

2. **Apple Sign In nonce handling production failures** — Works in development but fails with Apple reviewers' accounts, causing immediate rejection under Guideline 2.1. Some libraries make nonce optional; reviewer accounts enforce strict security. **Prevention:** Always implement cryptographic nonce, test with multiple Apple ID types (personal, managed, new), implement server-to-server notification endpoint (required for Korean users Jan 2026), handle authorization code expiration (5-minute window).

3. **Stripe Connect balance transfer timing failures** — Transfers execute before charge funds are available in connected account, causing "insufficient balance" errors. Drivers don't get paid, manual reconciliation required. **Prevention:** Tie transfers to charge ID as source (`source: charge_id`), implement Stripe webhooks for charge.succeeded before triggering transfers, set application_fee_amount on charge creation (not separate transfer).

4. **Location battery drain kills driver adoption** — Continuous high-accuracy GPS (every 1-5 seconds) drains 30-50% battery during 4-hour shift. Drivers uninstall or disable permissions, breaking core tracking. **Prevention:** Use significant-change location service when idle, set activityType to `.automotiveNavigation`, defer updates in background, reduce accuracy to `.nearestTenMeters` when precise location not needed, call stopUpdatingLocation() immediately when job completes, implement adaptive update frequency (1 sec active job, 30 sec available, off when offline).

5. **TestFlight rejection for "App Completeness"** — Over 40% of rejections fall under Guideline 2.1. Backend localhost URLs, missing privacy policy, insufficient test instructions, crashes on specific iOS versions. **Prevention:** Test on physical devices across iOS versions (not just simulator), provide detailed test credentials in App Review Notes, ensure production/staging URLs (never localhost), implement graceful degradation when backend unreachable, add privacy policy URL to App Store Connect, test full user journey from scratch (new account → complete transaction).

**Additional high-risk pitfalls:**
- Push notification certificate expiration (silent failure, use APNs Auth Key instead of .p12 certificates)
- MapKit location permission denial bricks app (handle all CLAuthorizationStatus cases, provide manual address entry fallback)
- SwiftUI state re-render loops during real-time updates (move state to ObservableObject, throttle updates, never modify state in view body)
- Reverse auction time pressure UX chaos (60-90 second minimum window, notification actions for bid submission, handle network failures gracefully)

## Implications for Roadmap

Based on research, suggested 5-phase structure reflecting technical dependencies, risk mitigation, and feature prioritization from FEATURES.md.

### Phase 1: Foundation & Authentication
**Rationale:** Everything depends on secure authentication and networking infrastructure. Cannot build features without data layer. Blocks all other phases.

**Delivers:**
- KeychainHelper utility for secure token storage
- APIClient actor with async/await and JWT token attachment
- AuthenticationManager with login/signup flows
- Apple Sign In integration with proper nonce handling (Pitfall 2 mitigation)
- Basic Codable models (User, Job, Booking)
- Environment-specific config management (dev/staging/prod URLs)

**Addresses features:**
- Authentication (table stakes)
- Secure token storage (security requirement)

**Avoids pitfalls:**
- Apple Sign In production failures (implement nonce upfront)
- UserDefaults token storage (use Keychain from start)
- Hardcoded API URLs (Config.swift pattern)

**Research flags:** LOW — Standard patterns well-documented, Apple official docs available

### Phase 2: Core Booking Flow (Customer App)
**Rationale:** Delivers minimum viable customer experience. Proves payment integration and backend connectivity before adding real-time complexity.

**Delivers:**
- Photo upload for junk estimation (manual admin review)
- Transparent pricing calculator (Base + Distance + Service Multiplier UI)
- Flexible scheduling (calendar picker with time slots)
- Address selection with MapKit MKLocalSearchCompleter
- Stripe PaymentService with Apple Pay integration
- Booking creation and confirmation flow
- Job history list and detail views

**Addresses features:**
- Photo-based estimation (table stakes)
- Transparent upfront pricing (table stakes)
- In-app payment (table stakes)
- Flexible scheduling (table stakes)
- Job history (table stakes)

**Uses stack:**
- Stripe iOS SDK 25.6+ (PaymentSheet, Apple Pay)
- MapKit (address autocomplete, distance calculation)
- Stripe Connect backend endpoints (create-intent, confirm)

**Avoids pitfalls:**
- Stripe balance transfer timing (tie transfers to charge ID from start)
- MapKit permission denial (handle all auth states, manual fallback)
- Payment guideline violations (clear App Review Notes about physical service exemption)

**Research flags:** LOW-MEDIUM — Stripe and MapKit well-documented, but payment flow needs TestFlight validation early

### Phase 3: Driver Dispatch & Acceptance (Driver App)
**Rationale:** Enables basic marketplace functionality without real-time auction complexity. First-come-first-serve dispatch validates core job flow before adding bidding.

**Delivers:**
- NotificationManager with APNs registration
- Push notification handling for new job alerts
- Job feed view with available jobs list
- Job detail view with accept/reject actions
- Navigation integration (deep link to Maps)
- Job status updates (accepted, en route, arrived, completed)
- Proof of service (before/after photo upload with GPS timestamp)

**Addresses features:**
- Job acceptance/rejection (table stakes)
- Push notifications (table stakes)
- Navigation integration (table stakes)
- Proof of service completion (table stakes)

**Uses stack:**
- APNs + UserNotifications framework
- CoreLocation for GPS timestamps
- URLSession multipart/form-data for photo uploads

**Implements architecture:**
- NotificationManager singleton
- Deep linking with NavigationStack
- ViewModel orchestration of API calls

**Avoids pitfalls:**
- APNs certificate expiration (use Auth Key from start, not .p12)
- TestFlight app completeness (test on physical devices, provide test accounts)
- Push notification unreliability (always fetch latest data on foreground, don't rely solely on silent push)

**Research flags:** LOW — Standard iOS notification patterns, Apple documentation sufficient

### Phase 4: Real-Time Features (Both Apps)
**Rationale:** Adds competitive differentiators after stable foundation. Socket.IO complexity isolated to this phase. High risk of background disconnection issues requires focused testing.

**Delivers:**
- SocketIOManager singleton with single connection
- Real-time job alerts for drivers (foreground only)
- Live GPS tracking with LocationManager background capability
- Driver location streaming to customers (map with moving marker)
- Reverse auction dispatch system (bid submission, timeout, auto-accept)
- Volume adjustment workflow (driver recalculates, customer approves)
- iOS Live Activities for Lock Screen job tracking (iOS 16+)

**Addresses features:**
- Real-time GPS tracking (table stakes enhancement)
- Reverse auction dispatch (key differentiator)
- Volume adjustment on-site (key differentiator)

**Uses stack:**
- Socket.IO Swift Client 16.1.1
- CoreLocation background modes
- Live Activities API (iOS 16+)

**Implements architecture:**
- SocketIOManager with @Observable state
- LocationManager with adaptive accuracy
- Background location tracking with CLServiceSession (iOS 18)

**Avoids pitfalls:**
- Socket.IO background disconnections (use APNs for critical events, Socket.IO for foreground only)
- Location battery drain (significant-change service, adaptive frequency, stop when job completes)
- SwiftUI state re-render loops (throttle location updates to 3-second UI refresh)
- Reverse auction time pressure (60-90 second window, notification actions, clear countdown)

**Research flags:** MEDIUM-HIGH — Complex integration, requires extensive battery and background testing. Socket.IO background behavior needs validation on physical devices across iOS versions. Volume adjustment workflow has no documented patterns (custom UX research needed).

### Phase 5: Ratings, Earnings & Polish
**Rationale:** Post-MVP enhancements after core marketplace proven. Builds trust and loyalty features.

**Delivers:**
- Two-way ratings/reviews (customer rates driver, driver rates customer)
- Driver earnings dashboard (real-time per-job, daily, weekly totals)
- Favorite/preferred drivers (save to favorites, "Request [Name]" for future jobs)
- Tip/gratuity feature (post-job digital tipping via Stripe)
- Eco-friendly disposal tracking (driver logs destination: recycled/donated/landfill)
- Cancellation policy enforcement (48-72 hour refund window, prorated after)
- Customer support integration (in-app help, email ticketing)

**Addresses features:**
- Two-way ratings/reviews (table stakes)
- Driver earnings dashboard (table stakes)
- Favorite/preferred drivers (differentiator)
- Tip/gratuity (differentiator)
- Eco-friendly tracking (differentiator)
- Cancellation policy (table stakes)
- Customer support (table stakes)

**Uses stack:**
- Stripe for tips (separate from job payment)
- URLSession for review submission
- UserDefaults for favorite driver IDs

**Research flags:** LOW — Standard CRUD patterns, no complex integrations

### Phase Ordering Rationale

**Why this order:**
1. **Foundation first (Phase 1):** Authentication and networking are hard dependencies for all features. Implementing these first prevents rework and ensures secure token handling from start.
2. **Customer before driver (Phase 2 before 3):** Proves payment integration and booking flow end-to-end. Easier to test customer experience without needing driver availability.
3. **Basic dispatch before auction (Phase 3 before 4):** First-come-first-serve validates core job lifecycle before adding real-time bidding complexity. Isolates Socket.IO risks to dedicated phase.
4. **Real-time as enhancement (Phase 4):** Socket.IO background disconnections are highest technical risk. Deferred until stable foundation prevents cascading issues.
5. **Ratings last (Phase 5):** Trust features require active user base to test effectively. Polish after marketplace mechanics proven.

**Dependency alignment:**
- Phase 1 outputs (AuthManager, APIClient) are inputs to all subsequent phases
- Phase 2 Stripe integration required before Phase 4 volume adjustment (recalculate invoice)
- Phase 3 push notifications required before Phase 4 real-time dispatch (fallback for Socket.IO disconnections)
- Phase 4 job completion required before Phase 5 ratings (can't rate incomplete jobs)

**Pitfall mitigation:**
- Apple Sign In nonce (Phase 1) prevents authentication failures in all phases
- Stripe charge ID transfers (Phase 2) prevents payment failures in Phase 4 volume adjustments
- APNs foundation (Phase 3) mitigates Socket.IO background issues (Phase 4)
- TestFlight testing at each phase boundary catches app completeness issues early

### Research Flags

**Phases likely needing deeper research during planning:**

- **Phase 4 (Real-Time Features):** Socket.IO background behavior on iOS 18 needs validation. Geofencing reliability issues reported in iOS 18. Volume adjustment workflow has no documented patterns (requires custom UX design and state management research). Two-app data sync strategies (customer + driver apps in sync via shared backend) need investigation. Background location optimization requires power profiling research.

- **Phase 4 (Reverse Auction):** iOS-specific auction UX patterns sparse (most research is web/Android). Need to research notification action bid submission, countdown timer implementation, network failure handling for time-sensitive bids.

**Phases with standard patterns (skip research-phase):**

- **Phase 1 (Foundation):** Apple Sign In, Keychain, URLSession async/await all have official Apple documentation and established patterns. Existing codebase already implements many of these correctly.

- **Phase 2 (Booking Flow):** Stripe iOS SDK and MapKit integration well-documented. PaymentSheet has official example code. Address autocomplete pattern verified in existing codebase (AddressInputViewModel).

- **Phase 3 (Dispatch):** Push notification registration and deep linking have comprehensive Apple guides. Standard iOS patterns sufficient.

- **Phase 5 (Ratings & Polish):** Basic CRUD operations, no complex integrations. Ratings/reviews are standard marketplace feature with many examples.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on Apple official docs, Stripe official SDK docs, existing codebase verification. All recommended technologies have production implementations in current apps. |
| Features | MEDIUM | Table stakes validated against LoadUp, 1-800-GOT-JUNK, TaskRabbit feature sets. Differentiators (reverse auction, volume adjustment) extrapolated from adjacent industries. Community consensus on marketplace requirements from multiple sources (Rigbyjs, Sharetribe, Ralabs). |
| Architecture | HIGH | MVVM with Clean Architecture validated across multiple Swift/iOS sources. @Observable macro pattern from Apple official migration guide. Actor-based networking from Swift concurrency best practices. Existing codebase already implements many recommended patterns (APIClient, AuthManager, SocketIOManager, LocationManager verified in code). |
| Pitfalls | MEDIUM-HIGH | High confidence on Apple platform-specific issues (APNs, MapKit, SwiftUI, location) based on official docs and energy guide. Medium confidence on third-party integrations (Stripe Connect, Socket.IO) based on official docs + community experiences. Lower confidence on marketplace-specific patterns (reverse auctions, two-sided architecture) with limited iOS-specific research. |

**Overall confidence:** HIGH

Research synthesis is based on 100+ sources across Apple official documentation, third-party official docs (Stripe, Socket.IO), community tutorials (Medium, Swift by Sundell, Hacking with Swift), and existing codebase verification. Stack and architecture recommendations are strongly validated. Feature requirements have community consensus but limited Umuve-specific validation. Pitfalls are well-researched for iOS platform issues but some marketplace patterns need phase-specific validation.

### Gaps to Address

**Volume adjustment workflow:** No specific iOS patterns found for driver-customer mid-job price renegotiation. Requires custom UX design during Phase 4 planning. Recommend researching field service apps (Jobber, Housecall Pro) for inspection → adjusted quote flows. Will need state management research for concurrent adjustment requests (driver proposes, customer approves/rejects, payment recalculation).

**Two-app data sync:** Limited research on keeping separate iOS apps (customer + driver) in sync via shared backend. Potential race conditions with job status updates. During Phase 4, research offline-first sync strategies and Socket.IO room-based targeting (emit updates only to relevant users). Consider SwiftData for local-first architecture if offline support becomes requirement.

**Driver app continuous operation:** How to keep driver app performant during 8+ hour shifts without memory leaks or battery death. Requires load testing during Phase 4. Research background task scheduling (BGTaskScheduler), memory profiling (Instruments), and thermal state monitoring. Adaptive behavior based on battery level may be needed.

**Background location on iOS 18:** iOS 18 has reported geofencing reliability issues with missed entry/exit events. Phase 4 requires testing on iOS 18 devices specifically. Consider polling fallback for critical geofence events. Research CLServiceSession and CLBackgroundActivitySession requirements for iOS 18+.

**Accessibility compliance:** VoiceOver support for real-time auction UI, map annotations, and time-sensitive notifications not researched. May be needed for App Store approval. If rejections occur, research Dynamic Type, VoiceOver labels for custom controls, and accessible countdown timers.

**App Store family sharing:** If customers request shared family hauling accounts, research StoreKit family sharing implementation. Not currently required but flag for future.

**Handling approach:** Gaps 1-4 require phase-specific research when planning Phase 4. Gap 5-6 are reactive (research if App Store feedback requires). All gaps are documented in PITFALLS.md "Gaps Requiring Phase-Specific Research" section for reference during roadmap execution.

## Sources

### Primary Sources (HIGH confidence)

**Apple Official Documentation:**
- [Stripe iOS SDK Documentation](https://docs.stripe.com/sdks/ios)
- [Stripe Connect for Marketplaces](https://stripe.com/connect/marketplaces)
- [Stripe: Create separate charges and transfers](https://docs.stripe.com/connect/separate-charges-and-transfers)
- [Apple Developer: AuthenticationServices](https://developer.apple.com/documentation/authenticationservices)
- [Apple Developer: Implementing User Authentication with Sign in with Apple](https://developer.apple.com/documentation/AuthenticationServices/implementing-user-authentication-with-sign-in-with-apple)
- [Apple Developer: TN3107 - Resolving Sign in with Apple response errors](https://developer.apple.com/documentation/technotes/tn3107-resolving-sign-in-with-apple-response-errors)
- [Apple Developer News: New requirement for apps using Sign in with Apple](https://developer.apple.com/news/?id=j9zukcr6)
- [Apple Developer: UserNotifications](https://developer.apple.com/documentation/usernotifications)
- [Apple Developer: MapKit MKDirections](https://developer.apple.com/documentation/mapkit/mkdirections)
- [Apple Developer: MKLocalSearchCompleter](https://developer.apple.com/documentation/mapkit/mklocalsearchcompleter)
- [Apple Developer: Storing Keys in the Keychain](https://developer.apple.com/documentation/security/certificate_key_and_trust_services/keys/storing_keys_in_the_keychain)
- [Apple Developer: Migrating to @Observable](https://developer.apple.com/documentation/swiftui/migrating-from-the-observable-object-protocol-to-the-observable-macro)
- [Apple Developer: CoreLocation Background Updates](https://developer.apple.com/documentation/corelocation/handling-location-updates-in-the-background)
- [Apple Developer: Energy Efficiency Guide - Location Best Practices](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/LocationBestPractices.html)
- [Apple Developer: TestFlight Overview](https://developer.apple.com/testflight/)
- [Apple Developer: App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [Apple Developer: Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)

**Package Repositories:**
- [Stripe iOS SDK on GitHub](https://github.com/stripe/stripe-ios)
- [Stripe iOS SDK Releases](https://github.com/stripe/stripe-ios/releases) (v25.6.0, Feb 11, 2026)
- [Socket.IO Swift Client on GitHub](https://github.com/socketio/socket.io-client-swift)
- [Socket.IO Swift Client Releases](https://github.com/socketio/socket.io-client-swift/releases) (v16.1.1)

### Secondary Sources (MEDIUM confidence)

**Architecture & Patterns:**
- [URLSession with Async/Await - Antoine van der Lee](https://www.avanderlee.com/concurrency/urlsession-async-await-network-requests-in-swift/)
- [Building Scalable Networking Layer - Patryk Skrzypek](https://medium.com/@skrzypekpatryk/building-a-scalable-generic-networking-layer-using-async-await-in-swift-5926b94a5715)
- [@Observable Macro Performance - Antoine van der Lee](https://www.avanderlee.com/swiftui/observable-macro-performance-increase-observableobject/)
- [Comparing @Observable to ObservableObject - Donny Wals](https://www.donnywals.com/comparing-observable-to-observableobjects/)
- [MVVM in SwiftUI - Matteo Manferdini](https://matteomanferdini.com/mvvm-pattern-ios-swift/)
- [iOS MVVM Clean Architecture - Ishafajar](https://medium.com/@ishafajar11/building-a-robust-ios-networking-layer-with-mvvm-and-clean-architecture-testable-code-a-pokemon-48be7cb43dde)
- [SwiftUI State Management Guide - Swift by Sundell](https://www.swiftbysundell.com/articles/swiftui-state-management-guide/)
- [Deep Linking for Local Notifications - Swift with Majid](https://swiftwithmajid.com/2024/04/09/deep-linking-for-local-notifications-in-swiftui/)
- [SwiftUI Deep Linking with Push Notifications - Mohit Sharma](https://medium.com/@mohitsdhami8/swiftui-deep-linking-with-push-notifications-a-step-by-step-guide-aa2e8b1f03ce)

**Security & Storage:**
- [Secure Token Storage Best Practices - Capgo](https://capgo.app/blog/secure-token-storage-best-practices-for-mobile-developers/)
- [Using Keychain for Token Storage - Ilgın Akgoz](https://medium.com/@ilginakgoz/using-keychain-how-to-securely-store-and-access-a-token-a0dc5bdf2d04)
- [Keychain Secure Storage in Swift](https://oneuptime.com/blog/post/2026-02-02-swift-keychain-secure-storage/view)
- [iOS Keychain Migration - Use Your Loaf](https://useyourloaf.com/blog/ios-and-keychain-migration-and-data-protection-part-3/)

**Push Notifications:**
- [iOS Push Notifications: Complete Setup Guide 2026](https://medium.com/@khmannaict13/ios-push-notifications-the-complete-setup-guide-for-2026-adfc98592ab7)
- [iOS Push Notifications Best Practices - Pushwoosh](https://www.pushwoosh.com/blog/ios-push-notifications/)
- [Silent Push Notifications: Opportunities, Not Guarantees](https://mohsinkhan845.medium.com/silent-push-notifications-in-ios-opportunities-not-guarantees-2f18f645b5d5)
- [Why Mobile Push Notification Architecture Fails - Netguru](https://www.netguru.com/blog/why-mobile-push-notification-architecture-fails)
- [Common Issues with Push in iOS - Notificare](https://notificare.com/blog/2023/09/25/common-issues-with-push-in-ios/)

**Location & Performance:**
- [Optimizing iOS Location Services - Rangle](https://rangle.io/blog/optimizing-ios-location-services)
- [Battery Consumption in iOS Apps](https://medium.com/@chandra.welim/battery-consumption-in-ios-apps-what-drains-battery-and-how-to-fix-it-72693e19de22)
- [SwiftUI CoreLocation - Code with Chris](https://codewithchris.com/swiftui-corelocation/)
- [MapKit Integration Checklist - Adalo](https://www.adalo.com/posts/mapkit-integration-checklist-ios-apps)
- [MapKit SwiftUI in iOS 17](https://medium.com/simform-engineering/mapkit-swiftui-in-ios-17-1fec82c3bf00)

**App Store & Distribution:**
- [Ultimate Guide to App Store Rejections - RevenueCat](https://www.revenuecat.com/blog/growth/the-ultimate-guide-to-app-store-rejections/)
- [Top Reasons for App Store Rejection - DECODE](https://decode.agency/article/app-store-rejection/)
- [Guideline 3.1 In-App Purchase Issues - iOS Submission Guide](https://iossubmissionguide.com/guideline-3-1-in-app-purchase/)
- [Apple Must Allow External Payment Links - RevenueCat](https://www.revenuecat.com/blog/growth/apple-anti-steering-ruling-monetization-strategy/)
- [Can You Use Stripe for In-App Purchases?](https://adapty.io/blog/can-you-use-stripe-for-in-app-purchases/)
- [iOS Distribution Guide 2025: TestFlight & Enterprise](https://foresightmobile.com/blog/ios-app-distribution-guide-2025)
- [CocoaPods is Dying: Migrate to SPM](https://capgo.app/blog/ios-spm-vs-cocoapods-capacitor-migration-guide/)
- [What Minimum iOS Version for Apps in 2026?](https://blog.ecoatm.com/what-minimum-ios-version-do-most-apps-need-in-2026/)

**Features & Marketplace:**
- [TaskRabbit Junk Removal Service](https://www.taskrabbit.com/services/moving/junk-removal)
- [LoadUp vs 1-800-GOT-JUNK Comparison](https://www.topconsumerreviews.com/best-junk-removal-companies/compare/loadup-vs-1-800-got-junk.php)
- [Checklist of 21 Services Marketplace Features](https://www.rigbyjs.com/blog/services-marketplace-features)
- [Marketplace App Booking Flow Best Practices - Sharetribe](https://www.sharetribe.com/academy/design-booking-flow-service-marketplace/)
- [Booking UX Best Practices 2025 - Ralabs](https://ralabs.org/blog/booking-ux-best-practices/)
- [Stripe Connect for Marketplaces Overview - Sharetribe](https://www.sharetribe.com/academy/marketplace-payments/stripe-connect-overview/)
- [Stripe Connect Split Payment Guide](https://www.yo-kart.com/blog/stripe-connect-split-payment-for-online-marketplaces-working-benefits/)

**Payment & Tipping:**
- [Subscription Payment using Stripe iOS SwiftUI SDK](https://medium.com/geekculture/subscription-payment-using-stripe-ios-swiftui-sdk-409a9fdc1a0)
- [Best Digital Tipping Solutions 2026](https://hoteltechreport.com/hr-staffing/digital-tipping)
- [Kickfin Tip Management Software](https://kickfin.com/)

### Tertiary Sources (LOW confidence - needs validation)

**Real-Time & Socket.IO:**
- [SwiftUI and Socket.IO - iOS Guru](https://medium.com/@ios_guru/swiftui-and-socket-io-ef036af3b57a)
- [Building Real-Time Bidding with Socket.IO](https://novu.co/blog/building-a-real-time-bidding-system-with-socket-io-and-react-native/)

**Reverse Auctions:**
- [What is a Reverse Auction - Complete Guide](https://simfoni.com/reverse-auction/)
- [Reverse Auction Common Mistakes - ProQSmart](https://proqsmart.com/blog/common-reverse-auction-mistakes-and-how-to-avoid-them/)

**Photo Volume Detection:**
- [ITTO Timber Volume App (Smartphone Photos)](https://www.itto.int/news/2023/06/09/itto_project_releases_app_for_calculating_timber_volumes_in_products_using_smartphones/)
- [Estimating Construction Waste Truck Payload Volume](https://www.researchgate.net/publication/355781935_Estimating_construction_waste_truck_payload_volume_using_monocular_vision)

### Existing Codebase Verification

Patterns verified in current Umuve codebase:
- `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Clean/JunkOS/Services/APIClient.swift`
- `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Services/DriverAPIClient.swift`
- `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Services/SocketIOManager.swift`
- `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Managers/AuthenticationManager.swift`
- `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Managers/LocationManager.swift`
- `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Managers/NotificationManager.swift`
- `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Clean/JunkOS/Services/PaymentService.swift`

---
*Research completed: 2026-02-13*
*Ready for roadmap: yes*
