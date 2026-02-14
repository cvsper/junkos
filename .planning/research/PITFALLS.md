# Domain Pitfalls: iOS Marketplace App (Hauling/Junk Removal)

**Domain:** Two-sided marketplace iOS apps (customer + driver) with real-time dispatch
**Researched:** 2026-02-13
**Confidence:** MEDIUM (based on official Apple docs, web search, community experiences)

---

## Critical Pitfalls

Mistakes that cause rewrites, App Store rejections, or major technical debt.

### Pitfall 1: Socket.IO Background Disconnections Leading to Lost Jobs
**What goes wrong:** WebSocket connections (Socket.IO) disconnect when iOS apps enter background or device locks. Drivers miss incoming job notifications, customers don't see live location updates, and the reverse auction dispatch system breaks.

**Why it happens:** iOS aggressively suspends background tasks to save battery. Socket.IO maintains an open TCP connection that iOS terminates when the app isn't in foreground. Developers assume WebSocket connections persist in background like they do on web or Android.

**Consequences:**
- Drivers miss job offers during the critical 30-60 second bidding window
- Customers can't track driver location in real-time during pickup
- Volume adjustment negotiations fail mid-conversation
- High battery drain if background modes are abused to keep sockets alive

**Prevention:**
1. Use APNs (push notifications) for critical events (new job, bid accepted, volume change request)
2. Reserve Socket.IO for foreground-only features (live chat, real-time map updates when app is active)
3. Implement notification-triggered background URLSession for job updates
4. Design UX assuming connection interruptions (show "reconnecting..." states, queue messages)
5. Never rely on background audio/location tricks to keep sockets alive (App Store violation)

**Detection:**
- Users report "missed notifications" when app is backgrounded
- Location tracking stops when phone locks
- High battery drain complaints
- App Store review notes about background execution

**Phase impact:** Critical for Phase 1 (real-time dispatch) and Phase 2 (live tracking)

---

### Pitfall 2: Apple Sign In Nonce Handling Causes Production-Only Failures
**What goes wrong:** Apple Sign In works perfectly in development but fails with Apple reviewers' accounts during TestFlight/App Store review. Users can't log in, blocking the entire app.

**Why it happens:** Some authentication libraries make nonce optional or omit it entirely. Development testing uses regular developer Apple IDs which may work without proper nonce validation, but Apple reviewer accounts enforce stricter security requirements.

**Consequences:**
- Immediate App Store rejection (Guideline 2.1 - App Completeness)
- Complete authentication failure for subset of users
- Emergency hotfix required post-launch
- Lost revenue during downtime

**Prevention:**
1. Always implement cryptographic nonce in Sign in with Apple flow
2. Test with multiple Apple ID types (personal, managed, new accounts)
3. Implement server-to-server notification endpoint (required for Korean users as of Jan 2026)
4. Handle authorization code expiration (5-minute window only)
5. Verify bundle ID matches in Xcode capabilities, Apple Developer portal, and all provisioning profiles
6. Monitor for Apple account status notifications (email changes, account deletions)

**Detection:**
- Authentication works for some users but not others
- "Invalid authorization code" errors in production
- Apple review rejection citing login failures
- Users report "Sign in with Apple button does nothing"

**Phase impact:** Blocking for Phase 1 (authentication)

**Sources:**
- [Apple Developer: New requirement for apps using Sign in with Apple](https://developer.apple.com/news/?id=j9zukcr6)
- [TN3107: Resolving Sign in with Apple response errors](https://developer.apple.com/documentation/technotes/tn3107-resolving-sign-in-with-apple-response-errors)

---

### Pitfall 3: Stripe Connect Balance Transfers Fail Due to Timing Issues
**What goes wrong:** Commission splits to platform account fail with "insufficient balance" errors even though customer paid successfully. Drivers don't get paid, platform doesn't receive commission, requiring manual reconciliation.

**Why it happens:** Transfers execute before charge funds are available in connected account balance. Developers assume immediate fund availability. Stripe processes ACH/card settlements asynchronously with delays of seconds to days.

**Consequences:**
- Failed payouts to drivers
- Manual intervention for every transaction
- Accounting reconciliation nightmare
- Driver trust erosion ("where's my money?")
- Potential Stripe account suspension for repeated failed transfers

**Prevention:**
1. **Tie transfers to charge ID as source** (not balance): `source: charge_id` ensures transfer only executes when funds available
2. Implement Stripe webhooks for charge.succeeded before triggering transfers
3. Set application_fee_amount on charge creation (not separate transfer) for 20% platform cut
4. Use destination charges or separate charges+transfers pattern consistently
5. Check connected account `charges_enabled` and `payouts_enabled` before processing payments
6. Set minimum payout thresholds ($25-50) to avoid micro-transaction overhead

**Detection:**
- "Insufficient balance" transfer errors in Stripe dashboard
- Discrepancy between charges and transfers in reconciliation reports
- Driver complaints about missing payments
- High volume of failed transfer webhooks

**Phase impact:** Blocking for Phase 2 (payment processing)

**Sources:**
- [Stripe: Create separate charges and transfers](https://docs.stripe.com/connect/separate-charges-and-transfers)
- [Stripe: Understand how charges work in Connect](https://docs.stripe.com/connect/charges)

---

### Pitfall 4: TestFlight Rejection Due to "App Completeness" Issues
**What goes wrong:** App works perfectly in development but gets rejected from TestFlight external testing with vague "app doesn't work" feedback. Over 40% of rejections fall under Guideline 2.1.

**Why it happens:**
- Crashes on specific iOS versions or devices not tested
- Backend endpoints use localhost or development URLs
- Features broken without backend connectivity
- Missing privacy policy URLs
- Test accounts required but not provided to reviewers
- App shows loading states indefinitely when APIs are down

**Consequences:**
- 1-2 week delay per rejection cycle
- Missed launch deadlines
- Team morale hit from repeated rejections
- Customer expectations unmet

**Prevention:**
1. **Test on physical devices extensively** (not just simulator) across iOS versions
2. Provide detailed test instructions in App Review Notes with credentials
3. Ensure all backend endpoints use production/staging URLs (never localhost)
4. Implement graceful degradation when backend is unreachable
5. Add privacy policy URL to App Store Connect metadata
6. Test full user journey from scratch (new account → complete transaction)
7. Remove all TestFlight-specific UI elements (no "Back to TestFlight" buttons)
8. Verify app works without being logged into a developer Apple ID

**Detection:**
- Reviewer feedback: "App doesn't load past splash screen"
- "We were unable to review your app" generic message
- Network errors in production environment
- Crash reports from App Store Connect showing nil unwrapping or network failures

**Phase impact:** Blocking for all phases (recurring risk with each submission)

**Sources:**
- [RevenueCat: The ultimate guide to App Store rejections](https://www.revenuecat.com/blog/growth/the-ultimate-guide-to-app-store-rejections/)
- [DECODE: Top reasons for app store rejection](https://decode.agency/article/app-store-rejection/)

---

## Moderate Pitfalls

Issues that degrade UX or cause technical debt but don't block launch.

### Pitfall 5: Location Tracking Battery Drain Kills Driver Adoption
**What goes wrong:** Driver app drains battery 30-50% during a 4-hour shift. Drivers uninstall app or disable location permissions, breaking the core tracking feature.

**Why it happens:** Continuous high-accuracy GPS updates (every 1-5 seconds) for real-time customer tracking. Developers prioritize accuracy over battery efficiency. Location hardware prevents device sleep even when not actively navigating.

**Consequences:**
- Driver churn and negative App Store reviews
- Drivers disable location services (breaking tracking)
- Increased support requests
- Competitive disadvantage vs battery-efficient competitors

**Prevention:**
1. Use **significant-change location service** or **visit monitoring** instead of continuous updates when driver is idle
2. Set `activityType` to `.automotiveNavigation` for optimized location hardware usage
3. Defer location updates when app is backgrounded using `allowDeferredLocationUpdates`
4. Reduce accuracy to `.nearestTenMeters` instead of `.best` when precise location isn't needed
5. Call `stopUpdatingLocation()` immediately when job is complete
6. Use geofencing for pickup/dropoff zones instead of continuous polling
7. Implement adaptive update frequency (1 second during active job, 30 seconds when available, off when offline)

**Detection:**
- Battery drain complaints in reviews
- Location permission revocation rate increase
- Thermal throttling during extended use
- Energy logs showing location as top consumer

**Phase impact:** High priority for Phase 2 (live tracking)

**Sources:**
- [Apple: Energy Efficiency Guide - Location Best Practices](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/LocationBestPractices.html)
- [Rangle: Optimizing iOS location services](https://rangle.io/blog/optimizing-ios-location-services)
- [Medium: Battery Consumption in iOS Apps](https://medium.com/@chandra.welim/battery-consumption-in-ios-apps-what-drains-battery-and-how-to-fix-it-72693e19de22)

---

### Pitfall 6: Push Notification Certificate Expiration Breaks Dispatch System
**What goes wrong:** Push notifications suddenly stop working across entire fleet. Drivers miss job offers, customers don't receive status updates. Discovery happens when users report "not getting notifications anymore."

**Why it happens:**
- .p12 APNs certificates expire after 1 year
- No monitoring alerts for expiration
- Wrong certificate environment (dev cert in prod, or vice versa)
- Device token doesn't match certificate topic/bundle ID

**Consequences:**
- Critical feature (job dispatch) completely broken
- Silent failure (no error to users, just missed notifications)
- Revenue loss from missed jobs
- Emergency certificate regeneration and app update

**Prevention:**
1. **Use APNs Auth Key instead of .p12 certificates** (never expires, works for all apps)
2. Set up monitoring alerts for notification delivery failures
3. Implement fallback notification checking via periodic background refresh
4. Store certificate expiration dates and alert 30 days before
5. Test notifications across development/staging/production environments separately
6. Verify bundle ID in notification request matches app bundle ID exactly
7. Handle device token refresh on app updates and OS updates

**Detection:**
- Users report "not receiving notifications"
- APNs returns error: "DeviceTokenNotForTopic"
- Notification delivery rate suddenly drops to 0%
- Backend logs show 403 Forbidden from APNs

**Phase impact:** Critical for Phase 1 (job dispatch notifications)

**Sources:**
- [Medium: iOS Push Notifications: The Complete Setup Guide for 2026](https://medium.com/@khmannaict13/ios-push-notifications-the-complete-setup-guide-for-2026-adfc98592ab7)
- [Notificare: Common issues with Push in iOS](https://notificare.com/blog/2023/09/25/common-issues-with-push-in-ios/)

---

### Pitfall 7: MapKit Location Permission Denial Bricks Core Features
**What goes wrong:** Users deny location permission (or grant "Ask Next Time"), and app shows blank maps or crashes. Since hauling requires pickup/delivery addresses, the app becomes unusable.

**Why it happens:**
- Developers don't handle all authorization states
- Missing or poorly worded Info.plist permission strings
- No graceful fallback for location denial
- Requesting location before explaining why

**Consequences:**
- App appears broken to users who deny permission
- Crashes from force-unwrapping nil location
- Low permission grant rate (users say "no" when asked too early)
- Can't fulfill core use case (scheduling pickups)

**Prevention:**
1. Add clear NSLocationWhenInUseUsageDescription and NSLocationAlwaysAndWhenInUseUsageDescription to Info.plist
2. Request permission at point of need (not on app launch) with contextual explanation
3. Handle all CLAuthorizationStatus cases: notDetermined, restricted, denied, authorizedWhenInUse, authorizedAlways
4. Provide manual address entry fallback if location denied
5. Show educational UI explaining why location is needed before requesting
6. Test app behavior with location disabled in simulator settings
7. For driver app: request "Always" authorization with clear explanation about background tracking

**Detection:**
- Crashes in CLLocationManager delegate methods
- Blank map views
- High percentage of users stuck at onboarding
- Permission request shown immediately on first launch

**Phase impact:** Blocking for Phase 1 (address selection, driver tracking)

**Sources:**
- [Adalo: MapKit Integration Checklist for iOS Apps](https://www.adalo.com/posts/mapkit-integration-checklist-ios-apps)
- [Code with Chris: SwiftUI CoreLocation](https://codewithchris.com/swiftui-corelocation/)

---

### Pitfall 8: SwiftUI State Management Causes Infinite Re-renders
**What goes wrong:** Views re-render hundreds of times per second during real-time updates (live map tracking, auction countdown timer, incoming bids). App becomes unresponsive, animations stutter, battery drains.

**Why it happens:**
- Modifying @State during view body computation triggers immediate re-render
- Large objects stored in @State cause full view recreation on any field change
- Network requests or side effects run directly in view body
- @Published properties fire on every nested object mutation

**Consequences:**
- Laggy, unresponsive UI during critical moments (accepting job, watching auction)
- Thermal throttling and battery drain
- Dropped frames in animations
- "Modifying state during view update" runtime warnings

**Prevention:**
1. Use @State only for simple local UI state (toggle states, text input)
2. Move complex state to @ObservableObject classes, update only changed @Published properties
3. Never modify state inside view body or during rendering
4. Move network calls and side effects to `.onAppear`, `.task`, or Button actions
5. Use `equatable` and `.id()` to prevent unnecessary re-renders
6. Debounce high-frequency updates (location every second → throttle to every 3 seconds for UI)
7. For real-time data, update model outside view hierarchy then publish state changes

**Detection:**
- Runtime warning: "Modifying state during view update, this will cause undefined behavior"
- Instruments showing high CPU usage in view updates
- UI thread blocking during state changes
- Xcode console spam with rapid print statements

**Phase impact:** High priority for Phase 2 (real-time tracking, auction UI)

**Sources:**
- [Swift by Sundell: A guide to SwiftUI's state management system](https://www.swiftbysundell.com/articles/swiftui-state-management-guide/)
- [Hacking with Swift: How to fix "Modifying state during view update"](https://www.hackingwithswift.com/quick-start/swiftui/how-to-fix-modifying-state-during-view-update-this-will-cause-undefined-behavior)

---

## Minor Pitfalls

Nuisances that create friction but are easily fixed.

### Pitfall 9: Keychain Data Persists After Uninstall, Breaking Fresh Start Testing
**What goes wrong:** Uninstalling and reinstalling app during development doesn't give clean slate. Old auth tokens, user preferences, or cached data persists from keychain, causing "ghost login" issues.

**Why it happens:** iOS keychain data survives app uninstall by design (intentional privacy feature as of iOS 10.3+). Developers expect uninstall to wipe all data like on Android.

**Consequences:**
- Can't properly test first-launch onboarding flow
- Logout functionality appears broken ("I deleted the app but I'm still logged in")
- Stale auth tokens cause 401 errors
- User confusion when switching between environments (dev/staging/prod)

**Prevention:**
1. Document that keychain persists across uninstalls (expected behavior, not a bug)
2. Implement "Clear all data" developer menu for testing
3. Add logout functionality that explicitly removes keychain items
4. Validate keychain auth tokens on app launch (check expiration, verify with backend)
5. Use environment-specific keychain keys (com.goumuve.app.dev vs com.goumuve.app.prod)
6. Test migration from old keychain keys (e.g., com.junkos.driver → com.goumuve.pro)

**Detection:**
- Testers report "app still logged in after deleting"
- First launch flow skipped after reinstall
- Different behavior between clean device and test device

**Phase impact:** Low priority, mainly affects development workflow

**Sources:**
- [Apple Developer Forums: iOS autodelete Keychain items after app deletion](https://developer.apple.com/forums/thread/36442)
- [Use Your Loaf: iOS and Keychain Migration and Data Protection](https://useyourloaf.com/blog/ios-and-keychain-migration-and-data-protection-part-3/)

---

### Pitfall 10: Reverse Auction Time Pressure Creates UX Chaos
**What goes wrong:** Drivers miss the 30-60 second auction window because they're driving, in another app, or didn't see notification. Customers wait indefinitely with no bids. Auction mechanics feel unfair or confusing.

**Why it happens:** Real-time auction logic is complex. Developers focus on happy path (driver immediately sees and responds) but ignore reality (driver notification delays, multitasking, poor cellular connection).

**Consequences:**
- Low bid participation rate
- Customer frustration from "no drivers available"
- Drivers complain about "missed opportunities"
- Unfair advantage to drivers with better devices/connectivity

**Prevention:**
1. Design auction window length based on real-world testing (60-90 seconds minimum)
2. Send multiple notification types: push, in-app banner, sound + vibration
3. Allow bid submission via notification action (no need to open app)
4. Show clear countdown timer and extension if bid activity detected
5. Implement "missed auction" notification after window closes
6. Provide auction history/replay for drivers who missed it
7. Pre-qualify drivers before auction (location radius, availability status)
8. Handle network failures gracefully (queue bids, show pending state)

**Detection:**
- Low auction completion rate
- Drivers report "never see auctions until too late"
- High percentage of auctions with 0 bids
- User reviews: "auction ended before I could bid"

**Phase impact:** Critical for Phase 1 (reverse auction dispatch)

**Sources:**
- [ProQSmart: Reverse Auction - Common Mistakes and How to Avoid Them](https://proqsmart.com/blog/common-reverse-auction-mistakes-and-how-to-avoid-them/)
- [Simfoni: What is a Reverse Auction - Complete Guide](https://simfoni.com/reverse-auction/)

---

### Pitfall 11: App Store Payment Processing Guideline Violations
**What goes wrong:** App gets rejected for bypassing in-app purchase (IAP) when using Stripe Connect for physical service payments. Reviewer misinterprets payment flow as digital content unlock.

**Why it happens:** App Store reviewers see payment screen and assume it's for digital goods (requires IAP). Physical goods/services are exempt from IAP requirements, but this isn't always clear to reviewers.

**Consequences:**
- Guideline 3.1 rejection
- Delayed launch while appealing or clarifying with App Review
- Potential forced migration to IAP (30% Apple cut instead of Stripe fees)

**Prevention:**
1. In App Review Notes, explicitly state: "Payments are for physical junk removal services (exempt from IAP per Guideline 3.1.1)"
2. Make UI/UX clearly show physical service nature (photos of junk, truck selection, address entry)
3. Include "Book Service" or "Schedule Pickup" language (not "Purchase" or "Unlock")
4. Reference Guideline 3.1.1 exemption for "goods and services used outside the app"
5. For US App Store: can now include external payment link with zero Apple commission (as of 2025 court ruling)
6. Avoid terminology like "subscription," "premium," or "unlock" that implies digital content

**Detection:**
- Guideline 3.1 rejection notice
- Reviewer asks "why not using IAP?"
- Payment flow gets flagged during review

**Phase impact:** Moderate risk for Phase 2 (payment processing)

**Sources:**
- [iOS Submission Guide: Guideline 3.1 Rejection - How to Fix In-App Purchase Issues](https://iossubmissionguide.com/guideline-3-1-in-app-purchase/)
- [RevenueCat: Apple must allow External Payment Links](https://www.revenuecat.com/blog/growth/apple-anti-steering-ruling-monetization-strategy/)
- [Apple: App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

---

### Pitfall 12: Silent Push Notification Unreliability Breaks Background Updates
**What goes wrong:** Backend sends job status updates via silent push notifications to update UI while app is backgrounded, but iOS silently drops them. Users open app to stale data.

**Why it happens:** iOS doesn't guarantee silent push delivery. System throttles them based on battery level, time of day, device memory, and whether user force-quit the app. Developers assume 100% delivery like regular notifications.

**Consequences:**
- Stale job status shown to drivers
- "New job" notification doesn't update UI until manual refresh
- Race conditions between silent push and user opening app
- Users think app is broken ("says job is pending but it's already accepted")

**Prevention:**
1. **Never rely solely on silent push for critical updates**
2. Always fetch latest data on app foreground (URLSession in `.onAppear` or `.task`)
3. Use silent push as optimization hint, not source of truth
4. Implement manual pull-to-refresh
5. Show timestamp of last update ("Updated 2 min ago")
6. Use regular (non-silent) push for time-sensitive updates with user action required
7. Test behavior after force-quitting app (silent push won't wake app)

**Detection:**
- Users report "old data shown until I refresh"
- Background fetch logs show dropped silent notifications
- Delivery rate < 80% in analytics
- Works in foreground but fails in background

**Phase impact:** Moderate for Phase 2 (background job updates)

**Sources:**
- [Medium: Silent Push Notifications in iOS - Opportunities, Not Guarantees](https://mohsinkhan845.medium.com/silent-push-notifications-in-ios-opportunities-not-guarantees-2f18f645b5d5)
- [Netguru: Why Most Mobile Push Notification Architecture Fails](https://www.netguru.com/blog/why-mobile-push-notification-architecture-fails)

---

## Phase-Specific Warnings

Pitfalls mapped to development phases where they're most likely to surface.

| Phase Topic | Likely Pitfall | Mitigation Strategy | Research Depth Needed |
|-------------|---------------|---------------------|----------------------|
| **Phase 1: Authentication** | Apple Sign In nonce handling (Pitfall 2) | Implement nonce, test with multiple Apple ID types, add server notifications endpoint | LOW - standard implementation |
| **Phase 1: Real-time Dispatch** | Socket.IO background disconnections (Pitfall 1) | Use APNs for critical events, Socket.IO for foreground only | MEDIUM - requires architecture redesign |
| **Phase 1: Reverse Auction UX** | Auction time pressure chaos (Pitfall 10) | Extend window to 60-90s, notification actions, countdown timers | LOW - UX iteration |
| **Phase 2: Payment Processing** | Stripe Connect balance transfer failures (Pitfall 3) | Tie transfers to charge ID, use webhooks, set application_fee upfront | LOW - follow Stripe best practices |
| **Phase 2: Payment Compliance** | App Store payment guideline violations (Pitfall 11) | Clear App Review Notes, physical service UX, cite Guideline 3.1.1 exemption | LOW - documentation clarity |
| **Phase 2: Live Tracking** | Location battery drain (Pitfall 5) | Significant-change service, deferred updates, adaptive frequency | MEDIUM - requires power testing |
| **Phase 2: Live Tracking** | MapKit permission denial (Pitfall 7) | Handle all auth states, contextual permission requests, manual address fallback | LOW - standard permission flow |
| **Phase 2: Real-time UI** | SwiftUI state re-render loops (Pitfall 8) | Move state to ObservableObject, throttle updates, no state modification in body | MEDIUM - performance profiling |
| **Phase 3: Background Sync** | Silent push unreliability (Pitfall 12) | Treat silent push as hint, always fetch on foreground, pull-to-refresh | LOW - expect unreliability |
| **All Phases: Notifications** | APNs certificate expiration (Pitfall 6) | Use Auth Key (never expires), monitor delivery failures | LOW - one-time switch |
| **All Phases: TestFlight** | App completeness rejections (Pitfall 4) | Physical device testing, test accounts, production URLs, privacy policy | MEDIUM - every submission |
| **All Phases: Development** | Keychain data persistence (Pitfall 9) | Document expected behavior, "clear data" dev menu, environment-specific keys | LOW - development convenience |

---

## Research Confidence Assessment

| Pitfall Area | Confidence | Sources |
|--------------|-----------|---------|
| Apple Sign In | HIGH | Official Apple TN3107, Developer News |
| Stripe Connect | MEDIUM | Stripe official docs, community patterns |
| Push Notifications | HIGH | Apple official docs, Medium (2026), developer forums |
| TestFlight/App Store | MEDIUM | RevenueCat guides, Apple forums, community experiences |
| Socket.IO Background | MEDIUM | Official Socket.IO docs, GitHub issues |
| MapKit/Location | HIGH | Apple official docs, energy efficiency guide |
| SwiftUI State | HIGH | Swift by Sundell, Hacking with Swift, official docs |
| Keychain | HIGH | Apple developer forums, official migration docs |
| Reverse Auctions | LOW | General auction best practices, not iOS-specific |
| Payment Guidelines | MEDIUM | App Store Guidelines, recent court rulings (2025) |
| Silent Push | HIGH | Official Apple docs, Medium articles, developer experiences |
| Battery Optimization | HIGH | Apple energy guide, multiple iOS optimization sources |

**Overall confidence: MEDIUM**
- High confidence on Apple platform-specific issues (APNs, MapKit, SwiftUI, location)
- Medium confidence on third-party integrations (Stripe, Socket.IO)
- Lower confidence on marketplace-specific patterns (reverse auctions, two-sided architecture)

---

## Gaps Requiring Phase-Specific Research

1. **Volume adjustment workflow** - No specific iOS patterns found for driver-customer mid-job price renegotiation. Will need custom UX design and state management research.

2. **Two-app data sync** (customer + driver apps) - Limited research on keeping separate iOS apps in sync via shared backend. May need deeper investigation into offline-first sync strategies.

3. **App Store family sharing** - If users want to share customer app access (family hauling account), need to research StoreKit family sharing implementation.

4. **Driver app continuous operation** - Longest research gap: how to keep driver app performant during 8+ hour shifts without memory leaks or battery death. Requires load testing and profiling research.

5. **Accessibility compliance** - VoiceOver support for real-time auction UI, map annotations, and time-sensitive notifications not researched. May be needed for App Store approval.

---

## Sources

### Apple Official Documentation
- [New requirement for apps using Sign in with Apple for account creation](https://developer.apple.com/news/?id=j9zukcr6)
- [TN3107: Resolving Sign in with Apple response errors](https://developer.apple.com/documentation/technotes/tn3107-resolving-sign-in-with-apple-response-errors)
- [Energy Efficiency Guide for iOS Apps: Reduce Location Accuracy and Duration](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/LocationBestPractices.html)
- [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### Third-Party Documentation
- [Stripe: Create separate charges and transfers](https://docs.stripe.com/connect/separate-charges-and-transfers)
- [Stripe: Understand how charges work in Connect](https://docs.stripe.com/connect/charges)
- [Socket.IO: Troubleshooting connection issues](https://socket.io/docs/v4/troubleshooting-connection-issues/)

### Community Resources (MEDIUM confidence)
- [Medium: iOS Push Notifications: The Complete Setup Guide for 2026](https://medium.com/@khmannaict13/ios-push-notifications-the-complete-setup-guide-for-2026-adfc98592ab7)
- [Medium: Battery Consumption in iOS Apps](https://medium.com/@chandra.welim/battery-consumption-in-ios-apps-what-drains-battery-and-how-to-fix-it-72693e19de22)
- [Medium: Silent Push Notifications in iOS: Opportunities, Not Guarantees](https://mohsinkhan845.medium.com/silent-push-notifications-in-ios-opportunities-not-guarantees-2f18f645b5d5)
- [RevenueCat: The ultimate guide to App Store rejections](https://www.revenuecat.com/blog/growth/the-ultimate-guide-to-app-store-rejections/)
- [RevenueCat: Apple must allow External Payment Links](https://www.revenuecat.com/blog/growth/apple-anti-steering-ruling-monetization-strategy/)

### Tutorials and Guides
- [Rangle: Optimizing iOS location services](https://rangle.io/blog/optimizing-ios-location-services)
- [Swift by Sundell: A guide to SwiftUI's state management system](https://www.swiftbysundell.com/articles/swiftui-state-management-guide/)
- [Hacking with Swift: How to fix "Modifying state during view update"](https://www.hackingwithswift.com/quick-start/swiftui/how-to-fix-modifying-state-during-view-update-this-will-cause-undefined-behavior)
- [Code with Chris: SwiftUI CoreLocation](https://codewithchris.com/swiftui-corelocation/)
- [Adalo: MapKit Integration Checklist for iOS Apps](https://www.adalo.com/posts/mapkit-integration-checklist-ios-apps)
- [iOS Submission Guide: Guideline 3.1 Rejection](https://iossubmissionguide.com/guideline-3-1-in-app-purchase/)
- [Use Your Loaf: iOS and Keychain Migration and Data Protection](https://useyourloaf.com/blog/ios-and-keychain-migration-and-data-protection-part-3/)
- [DECODE: Top reasons for app store rejection](https://decode.agency/article/app-store-rejection/)
- [Notificare: Common issues with Push in iOS](https://notificare.com/blog/2023/09/25/common-issues-with-push-in-ios/)
- [Netguru: Why Most Mobile Push Notification Architecture Fails](https://www.netguru.com/blog/why-mobile-push-notification-architecture-fails)

### Domain-Specific Resources (LOW confidence for iOS)
- [ProQSmart: Reverse Auction - Common Mistakes and How to Avoid Them](https://proqsmart.com/blog/common-reverse-auction-mistakes-and-how-to-avoid-them/)
- [Simfoni: What is a Reverse Auction - Complete Guide](https://simfoni.com/reverse-auction/)
