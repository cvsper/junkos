# Technology Stack

**Project:** Umuve iOS Apps (Customer + Driver)
**Researched:** 2026-02-13

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SwiftUI | iOS 16+ | Declarative UI framework | Native to Apple platforms, already implemented, excellent Xcode integration. iOS 17+ features (advanced MapKit) available but deploy to iOS 16 for 89.6% device coverage. |
| Swift | 6.0 | Primary language | Latest language version with full concurrency support, required by Xcode 16 for 2026 App Store submissions. |
| MVVM | N/A | Architecture pattern | Already implemented, clear separation of concerns, works harmoniously with SwiftUI's @Observable, @State, and Combine. |

**Confidence:** HIGH - Based on Apple Developer Documentation and existing codebase structure.

**Rationale:** SwiftUI is the modern standard for iOS development and already partially implemented in both apps. iOS 16 minimum deployment target balances feature access with device coverage (89.6% of devices as of Feb 2026).

### Authentication
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| AuthenticationServices | iOS 16+ | Apple Sign In | Native framework, App Store requirement for apps with third-party auth, zero-friction user experience, hardware-backed security. |
| Keychain Services | iOS 16+ | Secure token storage | Hardware-backed encryption via Secure Enclave, persists across app reinstalls, integrates with biometric auth (Face ID/Touch ID). |

**Confidence:** HIGH - Based on Apple Developer Documentation and App Store requirements.

**Rationale:**
- Apple Sign In is mandatory for App Store approval if offering other third-party sign-in options.
- Keychain is the only acceptable location for storing authentication tokens securely on iOS.
- Both are native frameworks requiring zero dependencies.

**Implementation:**
```swift
import AuthenticationServices
import Security

// Sign in with Apple
let appleIDProvider = ASAuthorizationAppleIDProvider()
let request = appleIDProvider.createRequest()
request.requestedScopes = [.fullName, .email]

// Keychain for token storage
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrAccount as String: "auth_token",
    kSecValueData as String: tokenData
]
SecItemAdd(query as CFDictionary, nil)
```

### Payment Processing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Stripe iOS SDK | 25.6+ | Payment collection & marketplace payouts | Official Stripe SDK, supports PaymentSheet for easy integration, handles PCI compliance, integrates with existing Flask backend Stripe implementation. |
| StoreKit 2 | iOS 16+ | (NOT USED for payments) | Apple's in-app purchase framework - NOT applicable for marketplace physical services. Stripe handles all payments. |

**Confidence:** HIGH - Based on Stripe official documentation and App Store guidelines for physical goods/services.

**Rationale:**
- Stripe iOS SDK v25.6.0 (released Feb 11, 2026) is the latest stable version.
- PaymentSheet provides prebuilt UI for 10+ payment methods with single integration.
- Stripe Connect already implemented in Flask backend for marketplace payments and driver payouts.
- Physical services (junk removal, hauling) are exempt from Apple's in-app purchase requirements.
- StoreKit is only required for digital goods; Stripe is the correct choice here.

**Installation (Swift Package Manager):**
```
https://github.com/stripe/stripe-ios
Version: 25.6.0+
```

**Backend Integration:**
Backend already has Stripe v5.5.0, supporting:
- Payment Intents for customer charges
- Stripe Connect for driver payouts
- Express Payouts for on-demand driver withdrawals (like Lyft's Express Pay)

### Maps & Location
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| MapKit | iOS 16+ | Maps, distance calculation, routing | Native Apple framework, zero cost, excellent SwiftUI integration, supports all required features. iOS 17+ has enhanced SwiftUI API but not required. |
| Core Location | iOS 16+ | GPS tracking, geofencing | Native framework for location services, supports background tracking with proper entitlements. |
| MKLocalSearchCompleter | iOS 16+ | Address autocomplete | Built into MapKit, easiest implementation for address search, no external dependencies. |
| MKDirections | iOS 16+ | Route calculation, distance, ETA | Native routing API, provides step-by-step directions and distance calculations. |

**Confidence:** MEDIUM-HIGH - Based on Apple Developer Documentation. iOS 18 has reported geofencing reliability issues per community reports.

**Rationale:**
- MapKit provides all required functionality (distance calc, routing, geocoding) at zero cost.
- Google Maps SDK is unnecessary overhead and adds $200/month minimum cost.
- MKLocalSearchCompleter already exists in codebase (AddressInputViewModel uses location services).
- LocationManager already partially implemented in driver app with background tracking setup.

**Known Issues (iOS 18):**
- Geofencing in iOS 18 has reported reliability issues with missed entry/exit events.
- Background location tracking requires CLServiceSession and CLBackgroundActivitySession for iOS 18+.
- Mitigation: Test thoroughly on iOS 18 devices, consider polling fallback for critical geofence events.

**Implementation Pattern:**
```swift
import MapKit
import CoreLocation

// Distance calculation
let request = MKDirections.Request()
request.source = MKMapItem(placemark: MKPlacemark(coordinate: origin))
request.destination = MKMapItem(placemark: MKPlacemark(coordinate: destination))
request.transportType = .automobile

let directions = MKDirections(request: request)
directions.calculate { response, error in
    let route = response?.routes.first
    let distance = route?.distance // meters
    let eta = route?.expectedTravelTime // seconds
}

// Address autocomplete
let completer = MKLocalSearchCompleter()
completer.queryFragment = userInput
// Implement MKLocalSearchCompleterDelegate for results
```

### Push Notifications
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| UserNotifications | iOS 16+ | Local & remote push notifications | Native framework, required for APNs integration, supports rich notifications and deep linking. |
| APNs (Apple Push Notification service) | N/A | Delivery infrastructure | Apple's push notification service, free, reliable, no alternatives for iOS. |

**Confidence:** HIGH - Based on Apple Developer Documentation and iOS 18 2026 updates.

**Rationale:**
- UserNotifications is the only framework for push notifications on iOS.
- Backend already has APNs implementation (push_notifications.py).
- iOS 18 (2026) introduces "priority notifications" and enhanced controls.
- NotificationManager already partially implemented in both apps.
- Maximum payload: 4KB per notification.

**Backend Integration:**
Backend has:
- Flask APNs integration for sending push notifications
- Token registration endpoints
- Deep link payload support for job updates

**Implementation Notes:**
- Request authorization: `.alert`, `.sound`, `.badge`
- Register for remote notifications in AppDelegate/App
- Handle deep links via `userNotificationCenter(_:didReceive:)` delegate
- Category-based actions already defined (booking_confirmed, driver_en_route, job_completed)

### Real-Time Communication
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Socket.IO Swift Client | 16.1.1 | Real-time bidding, job updates, driver location | Official Swift client for Socket.IO, backend already uses Flask-SocketIO v5.3.6, proven for marketplace real-time features. |
| Combine | iOS 16+ | Reactive data flow | Native framework for handling async event streams, perfect for socket events feeding ViewModels. |
| Swift Concurrency (async/await) | Swift 5.5+ | API calls, single responses | Modern async pattern for one-time requests, cleaner than completion handlers. |

**Confidence:** MEDIUM - Socket.IO Swift client is community-maintained, not Apple. Backend integration is proven.

**Rationale:**
- Backend already implements Socket.IO for real-time job dispatch and driver location streaming.
- Socket.IO Swift client v16.1.1 is latest stable (no v17 as of Feb 2026).
- Alternative (native WebSockets) requires rewriting backend Socket.IO layer.
- Combine for multi-value streams (socket events), async/await for single API responses.

**Installation (Swift Package Manager):**
```
https://github.com/socketio/socket.io-client-swift
Version: 16.1.1
```

**Architecture Pattern:**
```swift
import SocketIO
import Combine

// Use Combine for socket event streams
class JobFeedViewModel: ObservableObject {
    private let socketManager: SocketManager
    @Published var incomingJobs: [Job] = []

    func connectToJobFeed() {
        socket.on("new_job") { [weak self] data, ack in
            // Parse job, update @Published property
            // SwiftUI view reacts automatically
        }
    }
}

// Use async/await for API calls
func confirmJob(id: String) async throws -> JobConfirmation {
    let url = URL(string: "\(baseURL)/api/jobs/\(id)/confirm")!
    let (data, _) = try await URLSession.shared.data(from: url)
    return try JSONDecoder().decode(JobConfirmation.self, from: data)
}
```

### Dependency Management
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Swift Package Manager (SPM) | Xcode 16+ | Dependency management | Native to Xcode, faster than CocoaPods, CocoaPods becomes read-only Dec 2026, zero configuration files. |

**Confidence:** HIGH - Official Apple tooling, industry migration to SPM in 2026.

**Rationale:**
- CocoaPods becomes read-only December 2, 2026 (no new pods or updates).
- SPM is 10-50% faster build times compared to CocoaPods.
- Native Xcode integration, no Podfile/workspace complexity.
- All required libraries support SPM (Stripe, Socket.IO).

**Migration Status:**
Current projects use `.xcodeproj` (no Podfile detected), ready for SPM.

**Dependencies to Add:**
1. Stripe iOS SDK (25.6.0+)
2. Socket.IO Swift Client (16.1.1)

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| KeychainSwift | 20.0+ (OPTIONAL) | Keychain wrapper | Only if you want simplified keychain API. Native Security framework is sufficient. |
| Sentry iOS | 8.0+ (OPTIONAL) | Crash reporting | Backend already uses Sentry; add iOS SDK for client-side crash tracking. |

**Confidence:** MEDIUM - Nice-to-haves, not critical path.

**Rationale:**
- KeychainSwift simplifies keychain access but adds dependency. Native Security framework works fine.
- Sentry iOS SDK integrates with existing backend Sentry (already in backend requirements.txt).
- Both are optional; assess after core features complete.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Dependency Management | Swift Package Manager | CocoaPods | CocoaPods goes read-only Dec 2026, slower builds, requires workspace files. |
| Maps | MapKit | Google Maps SDK | $200/month cost, unnecessary complexity, MapKit has all needed features. |
| Real-Time | Socket.IO | Native WebSockets | Backend already implements Socket.IO; rewriting backend is higher cost than client library. |
| Authentication | Apple Sign In + Keychain | Firebase Auth | Backend already has auth system, Firebase adds unnecessary dependency and vendor lock-in. |
| Payments | Stripe | In-App Purchase (StoreKit) | Physical services exempt from IAP requirement, Stripe Connect already in backend. |
| State Management | Combine + @Observable | Redux/TCA | SwiftUI's native state management is sufficient for this app's complexity. |

## Installation

### Swift Package Manager (Xcode)

**Step 1:** Open Xcode project
**Step 2:** File → Add Package Dependencies
**Step 3:** Add these packages:

```
Stripe iOS SDK
https://github.com/stripe/stripe-ios
Version: 25.6.0+

Socket.IO Swift Client
https://github.com/socketio/socket.io-client-swift
Version: 16.1.1
```

**Step 4:** Select target (Umuve or Umuve Pro) for each package

### Xcode Capabilities Required

**Both Apps:**
- Sign In with Apple (Signing & Capabilities → + Capability)
- Push Notifications (Signing & Capabilities → + Capability)
- Background Modes → Remote notifications

**Driver App Only:**
- Background Modes → Location updates
- Background Modes → Background fetch (for socket connection)

### Info.plist Required Keys

**Both Apps:**
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>We need your location to show nearby services and calculate distances.</string>
```

**Driver App Only:**
```xml
<key>NSLocationAlwaysUsageDescription</key>
<string>We need your location to match you with nearby jobs and track deliveries.</string>

<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>We track your location to provide real-time updates to customers during active jobs.</string>

<key>UIBackgroundModes</key>
<array>
    <string>location</string>
    <string>remote-notification</string>
    <string>fetch</string>
</array>
```

## Framework Versions & Requirements

### iOS Deployment Target
**Recommended:** iOS 16.0
**Coverage:** 89.6% of devices (Feb 2026)
**Rationale:** Balances feature access with market coverage. iOS 17+ features (advanced MapKit SwiftUI) are nice-to-have, not required.

### Xcode Version
**Required:** Xcode 16+
**Reason:** App Store submissions after April 28, 2026 require iOS 26 SDK (Xcode 16).

### Swift Version
**Required:** Swift 6.0
**Reason:** Latest concurrency features, required by Xcode 16.

## Backend Integration Points

Backend (Flask) already implements:

| Feature | Endpoint/Service | iOS Integration |
|---------|------------------|-----------------|
| Authentication | `/auth/register`, `/auth/login` | AuthenticationManager via URLSession |
| Stripe Payments | `/api/payments/create-intent` | Stripe iOS SDK PaymentSheet |
| Stripe Connect Payouts | `/api/payouts/express` | Driver app earnings view |
| Push Notifications | APNs via `push_notifications.py` | UserNotifications framework |
| Socket.IO Events | `socket_events.py` (new_job, location_update) | Socket.IO Swift client |
| Job Dispatch | `/api/jobs/*` endpoints | Job feed and detail views |

**API Version:** Backend uses Flask 3.0.0, Python 3.11+
**Authentication:** JWT tokens (Flask-JWT-Extended 4.6.0)
**Token Storage:** iOS stores JWT in Keychain, sends via `Authorization: Bearer` header

## Testing Requirements for TestFlight

| Requirement | Status | Notes |
|-------------|--------|-------|
| iOS 26 SDK | Required April 28, 2026 | Use Xcode 16+ |
| Beta App Description | Required | Add in App Store Connect before external testing |
| Beta Review Info | Required | First build requires App Review approval |
| Provisioning Profile | Required | Include app identifiers in profiles |
| External Testers | Up to 10,000 | Create groups in App Store Connect |

**Deployment Process:**
1. Archive app in Xcode 16+
2. Upload to App Store Connect
3. Add beta app description and review info
4. First build auto-submitted for TestFlight review (~24-48 hours)
5. After approval, invite testers via groups
6. Subsequent builds skip review unless major changes

## Production Readiness Checklist

- [ ] Swift Package Manager dependencies added (Stripe, Socket.IO)
- [ ] Sign In with Apple capability enabled in Xcode
- [ ] Push Notifications capability enabled in Xcode
- [ ] APNs certificates configured in Apple Developer Portal
- [ ] Background Modes enabled for driver app (location, remote-notification)
- [ ] Info.plist location permission strings added
- [ ] Keychain access implemented for auth token storage
- [ ] Stripe publishable key configured (use .xcconfig or Config.swift)
- [ ] Socket.IO connection to backend tested
- [ ] Deep linking for push notifications implemented
- [ ] TestFlight beta description written
- [ ] App icons and launch screens finalized
- [ ] Privacy Policy URL added to App Store Connect

## Anti-Patterns to Avoid

### Do NOT Use:
1. **Firebase** - Backend already implements auth, push, and database. Adding Firebase creates vendor lock-in and duplicate systems.
2. **Google Maps SDK** - MapKit provides all needed features at zero cost. Google Maps adds $200/month minimum cost and API key management.
3. **CocoaPods** - Goes read-only Dec 2026. Use SPM.
4. **Redux/TCA** - Over-engineered for this app. SwiftUI's native state management is sufficient.
5. **Realm/Core Data** - Backend is source of truth. Use in-memory models or simple UserDefaults for caching.
6. **StoreKit for payments** - Only for digital goods. Stripe is correct for physical services.

### Common Mistakes:
1. **Storing tokens in UserDefaults** - Security violation. Always use Keychain.
2. **Requesting location permission too early** - Request when needed (address input screen), not on app launch.
3. **Blocking main thread with sync Socket.IO calls** - Use Combine publishers or async/await wrappers.
4. **Hardcoding API URLs** - Use Config.swift with environment-specific URLs (dev/staging/prod).
5. **Skipping error handling on payment flows** - Stripe can fail; handle all error cases gracefully.

## Version Matrix

| Component | Production | Notes |
|-----------|-----------|-------|
| iOS Deployment Target | 16.0 | 89.6% device coverage |
| Swift Language | 6.0 | Required by Xcode 16 |
| Xcode | 16+ | Required for App Store as of April 28, 2026 |
| Stripe iOS SDK | 25.6.0+ | Latest stable (Feb 11, 2026) |
| Socket.IO Swift | 16.1.1 | Latest stable (Oct 2025) |
| Backend Flask | 3.0.0 | Already deployed |
| Backend Stripe | 5.5.0 | Already deployed |
| Backend Socket.IO | 5.3.6 | Already deployed |

## Sources

### Official Documentation (HIGH Confidence)
- [Stripe iOS SDK Documentation](https://docs.stripe.com/sdks/ios)
- [Stripe Connect for Marketplaces](https://stripe.com/connect/marketplaces)
- [Apple Developer - AuthenticationServices](https://developer.apple.com/documentation/authenticationservices)
- [Apple Developer - Implementing User Authentication with Sign in with Apple](https://developer.apple.com/documentation/AuthenticationServices/implementing-user-authentication-with-sign-in-with-apple)
- [Apple Developer - UserNotifications](https://developer.apple.com/documentation/usernotifications)
- [Apple Developer - MapKit MKDirections](https://developer.apple.com/documentation/mapkit/mkdirections)
- [Apple Developer - MKLocalSearchCompleter](https://developer.apple.com/documentation/mapkit/mklocalsearchcompleter)
- [Apple Developer - Storing Keys in the Keychain](https://developer.apple.com/documentation/security/certificate_key_and_trust_services/keys/storing_keys_in_the_keychain)
- [Apple Developer - TestFlight Overview](https://developer.apple.com/testflight/)

### Package Repositories (HIGH Confidence)
- [Stripe iOS SDK on GitHub](https://github.com/stripe/stripe-ios)
- [Stripe iOS SDK Releases](https://github.com/stripe/stripe-ios/releases)
- [Socket.IO Swift Client on GitHub](https://github.com/socketio/socket.io-client-swift)
- [Socket.IO Swift Client Releases](https://github.com/socketio/socket.io-client-swift/releases)

### Web Sources (MEDIUM Confidence)
- [iOS Push Notifications: The Complete Setup Guide for 2026](https://medium.com/@khmannaict13/ios-push-notifications-the-complete-setup-guide-for-2026-adfc98592ab7)
- [CocoaPods is Dying: Why You Should Migrate to SPM](https://capgo.app/blog/ios-spm-vs-cocoapods-capacitor-migration-guide/)
- [What Minimum iOS Version Do Most Apps Need in 2026?](https://blog.ecoatm.com/what-minimum-ios-version-do-most-apps-need-in-2026/)
- [Mastering SwiftUI: Combine vs Async/Await in 2026](https://medium.com/@viralswift/mastering-swiftui-combine-vs-async-await-when-to-use-what-in-2026-c458d64eaf35)
- [MapKit SwiftUI in iOS 17](https://medium.com/simform-engineering/mapkit-swiftui-in-ios-17-1fec82c3bf00)
- [How to Use Keychain for Secure Storage in Swift](https://oneuptime.com/blog/post/2026-02-02-swift-keychain-secure-storage/view)
- [Building a Real-Time Bidding System with Socket.IO](https://novu.co/blog/building-a-real-time-bidding-system-with-socket-io-and-react-native/)
- [iOS Distribution Guide 2025: TestFlight & Enterprise](https://foresightmobile.com/blog/ios-app-distribution-guide-2025)

### App Store Requirements (HIGH Confidence)
- [Apple Developer News - Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)
- [Can You Use Stripe for In-App Purchases in 2026?](https://adapty.io/blog/can-you-use-stripe-for-in-app-purchases/)
