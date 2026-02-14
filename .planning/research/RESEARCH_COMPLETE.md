# RESEARCH COMPLETE

**Project:** Umuve iOS Apps Completion
**Mode:** Stack Research (iOS marketplace apps)
**Confidence:** HIGH
**Date:** 2026-02-13

## Key Findings

### Stack Recommendations

1. **Swift Package Manager over CocoaPods** - CocoaPods becomes read-only December 2, 2026. SPM is native, faster, and future-proof.

2. **iOS 16.0 minimum deployment target** - Provides 89.6% device coverage while supporting all required features. iOS 17+ has enhanced MapKit but not critical.

3. **Native frameworks over third-party** - MapKit (not Google Maps), AuthenticationServices (required for App Store), Keychain Services (not Firebase Auth). Backend already implements auth and database.

4. **Stripe iOS SDK 25.6.0** - Latest stable release (Feb 11, 2026), integrates with existing Flask backend Stripe Connect implementation for marketplace payments and driver payouts.

5. **Socket.IO Swift Client 16.1.1** - Official client matching backend Flask-SocketIO v5.3.6 for real-time job bidding and driver location tracking.

### Critical Findings

**CocoaPods Sunset:** December 2, 2026 is the deadline for CocoaPods read-only status. Project must use Swift Package Manager.

**App Store Requirements:** Starting April 28, 2026, all submissions require Xcode 16 and iOS 26 SDK. Current project is iOS 16 deployment target (correct).

**Payment Processing:** Stripe is correct choice for physical services (junk removal, hauling). StoreKit only applies to digital goods/in-app content.

**iOS 18 Geofencing Issues:** Community reports indicate geofencing reliability problems in iOS 18. Recommend testing thoroughly and implementing polling fallback for critical location-based features.

## Files Created

| File | Purpose |
|------|---------|
| .planning/research/STACK.md | Comprehensive technology stack with versions, installation instructions, rationale, and anti-patterns |

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Core Frameworks | HIGH | Official Apple documentation, existing codebase uses SwiftUI/MVVM |
| Stripe Integration | HIGH | Official Stripe docs, backend already implements Stripe Connect v5.5.0 |
| Socket.IO | MEDIUM | Community-maintained Swift client, but backend integration proven, v16.1.1 is stable |
| MapKit | MEDIUM-HIGH | Official Apple framework, but iOS 18 has reported geofencing issues |
| Dependency Management | HIGH | SPM is official Apple tooling, CocoaPods sunset date confirmed |

## Roadmap Implications

### Phase Structure Recommendations

**Phase 1: Core Infrastructure**
- Add Swift Package Manager dependencies (Stripe, Socket.IO)
- Implement Keychain-based auth token storage
- Configure Xcode capabilities (Sign In with Apple, Push Notifications, Background Modes)

**Phase 2: Authentication & Payments**
- Implement Apple Sign In flow
- Integrate Stripe PaymentSheet for customer payments
- Add Stripe Connect integration for driver earnings

**Phase 3: Real-Time Features**
- Connect Socket.IO client to backend for job bidding
- Implement push notification handling and deep linking
- Add driver location tracking and streaming

**Phase 4: Maps & Navigation**
- Implement MapKit distance calculations and routing
- Add MKLocalSearchCompleter for address autocomplete
- Integrate driver navigation during active jobs

**Phase 5: TestFlight Deployment**
- Configure beta app descriptions
- Submit first build for TestFlight review
- Set up external tester groups

### Phase Ordering Rationale

1. **Infrastructure first** - Dependencies and capabilities must be in place before feature implementation
2. **Auth before payments** - Can't charge users without knowing who they are
3. **Real-time before maps** - Job dispatch and bidding is core value prop, maps support active jobs
4. **TestFlight last** - All core features must work before external testing

### Research Flags for Phases

**No deep research needed** - Stack uses primarily native iOS frameworks with official documentation:
- AuthenticationServices (native)
- Keychain Services (native)
- MapKit (native)
- Core Location (native)
- UserNotifications (native)

**Monitor for issues:**
- Socket.IO Swift client (community-maintained, not Apple)
- iOS 18 geofencing reliability (known issue)
- Stripe SDK updates (breaking changes possible)

## Open Questions

### Low Priority / Defer to Implementation

1. **Crash Reporting** - Should Sentry iOS SDK be added to match backend? Not blocking for TestFlight.

2. **Keychain Wrapper Library** - Use native Security framework or add KeychainSwift library? Native is sufficient but wrapper may speed development.

3. **Background Location Strategy** - iOS 18 requires CLServiceSession/CLBackgroundActivitySession. Current LocationManager may need updates for iOS 18 compatibility.

4. **Socket Connection Persistence** - Should Socket.IO maintain connection in background or reconnect on-demand? Needs power consumption testing.

### Already Answered

- Payment processing: Stripe (not StoreKit)
- Maps: MapKit (not Google Maps)
- Dependency management: SPM (not CocoaPods)
- State management: SwiftUI native (not Redux/TCA)

## Next Steps

1. **Orchestrator** should create roadmap with 5 phases as outlined above
2. **Implementation** can begin immediately - all required packages and frameworks identified
3. **No additional research** needed for core features - all use official Apple frameworks with comprehensive documentation

## Technical Debt Identified

**From existing codebase review:**
- NotificationManager and LocationManager already partially implemented
- AuthenticationManager references Config.shared (exists at JunkOS-Clean/JunkOS/Services/Config.swift)
- No Podfile detected - project ready for SPM
- Bundle IDs updated for rebrand (com.goumuve.app, com.goumuve.pro)

**No migration needed:**
- Already using SwiftUI + MVVM
- No CocoaPods to migrate from
- Backend APIs already support required features

## Budget & Cost Implications

**Zero ongoing costs for:**
- MapKit (native, no API costs)
- AuthenticationServices (native)
- Push Notifications via APNs (free)
- All native iOS frameworks

**Existing costs (already paid):**
- Apple Developer Program: $99/year (required for TestFlight and App Store)
- Stripe fees: 2.9% + 30¢ per transaction (already implemented in backend)

**No new subscriptions required.**
