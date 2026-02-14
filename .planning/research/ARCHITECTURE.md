# Architecture Patterns

**Domain:** iOS Marketplace Apps (Customer + Driver) with SwiftUI
**Researched:** 2026-02-13

## Recommended Architecture

SwiftUI MVVM with Clean Architecture layers, separating concerns into distinct components with clear boundaries. The architecture uses modern Swift concurrency (async/await) throughout, replacing completion handlers and combine publishers where possible.

```
┌─────────────────────────────────────────────────────────────┐
│                         SwiftUI Views                        │
│  (Presentation Layer - Declarative UI, User Interaction)    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                       ViewModels                             │
│  (MVVM Pattern - @Observable, Business Logic, State)        │
└────────────┬───────────────────────────┬────────────────────┘
             │                           │
             ▼                           ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│   Managers           │    │   Services                    │
│ (Singleton patterns) │    │ (Networking, Payments, etc.) │
│  - AuthManager       │    │  - APIClient                 │
│  - LocationManager   │    │  - SocketIOManager           │
│  - NotificationMgr   │    │  - PaymentService            │
└──────────┬───────────┘    └───────────┬──────────────────┘
           │                            │
           └────────────┬───────────────┘
                        ▼
           ┌─────────────────────────┐
           │      Models (Codable)    │
           │   (Data Transfer Objects)│
           └─────────────────────────┘
                        │
                        ▼
           ┌─────────────────────────┐
           │   Backend (Flask)        │
           │   REST API + Socket.IO   │
           │   junkos-backend.com     │
           └─────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With | Pattern |
|-----------|---------------|-------------------|---------|
| **Views** | Render UI, handle user input, navigation | ViewModels (read state) | SwiftUI declarative views |
| **ViewModels** | UI state, business logic, orchestrate services | Services, Managers, Views | @Observable (iOS 17+) |
| **Managers** | Cross-cutting concerns (auth, location, notifications) | APIClient, System APIs | Singleton with @Observable |
| **Services** | Domain-specific operations (network, payment) | Backend APIs, System SDKs | Actor (thread-safe) or Class |
| **APIClient** | HTTP networking, token attachment, error handling | Backend REST endpoints | Actor with URLSession async/await |
| **SocketIOManager** | WebSocket connection, real-time events | Backend Socket.IO server | @Observable singleton |
| **Models** | Data structures, JSON encoding/decoding | All layers | Codable structs |
| **KeychainHelper** | Secure token persistence | AuthManager, APIClient | Static utility class |

### Data Flow

**Authentication Flow:**
```
User Action (View)
  → AuthViewModel.login(email, password)
    → APIClient.login() [async/await]
      → Backend /api/auth/login
    ← AuthResponse (JWT token + user)
  → AuthManager.setAuthenticated(user, token)
    → KeychainHelper.save(token)
    → NotificationManager.reRegisterTokenIfNeeded()
  → View updates (isAuthenticated = true)
```

**Real-Time Job Alert Flow (Driver App):**
```
AppState.startLocationTracking()
  → SocketIOManager.connect(token)
    → Backend Socket.IO server (auth via JWT query param)
  → SocketIOManager.on("job:new")
    ← Backend emits job alert
  → SocketIOManager.newJobAlert = job
  → JobFeedViewModel polls AppState.consumeJobAlert()
    → View shows job alert card
```

**Location Streaming Flow:**
```
LocationManager.startTracking()
  → CLLocationManager.didUpdateLocations
    → LocationManager.onLocationUpdate callback
      → SocketIOManager.emitLocation(lat, lng, contractorId, jobId)
        → Backend "driver:location" event
      → APIClient.updateLocation(lat, lng) [async/await]
        → Backend POST /api/drivers/location
```

**Payment Flow:**
```
User taps "Pay" (ConfirmationView)
  → PaymentService.createPaymentIntent(amount, bookingId)
    → Backend POST /api/payments/create-intent-simple
    ← clientSecret, paymentIntentId
  → PKPaymentAuthorizationViewController.present() [Apple Pay]
    ← User authorizes with Face ID/Touch ID
  → PaymentService.confirmPayment(paymentIntentId)
    → Backend POST /api/payments/confirm-simple
    ← success = true
  → BookingViewModel.createBooking()
    → Backend POST /api/bookings
```

**Push Notification Deep Link Flow:**
```
APNs delivers notification
  → AppDelegate.didReceive(notification)
    → NotificationManager.userNotificationCenter(didReceive:)
      → NotificationCenter.post(.didTapPushNotification, userInfo)
  → AppState observes notification
    → Extracts jobId from userInfo
    → NavigationPath.append(jobId)
  → SwiftUI NavigationStack routes to JobDetailView(jobId)
```

## Patterns to Follow

### Pattern 1: Actor-Based Networking Layer
**What:** Use `actor` for thread-safe network clients to prevent data races.

**When:** All APIClient classes that manage mutable session state or caching.

**Example:**
```swift
actor DriverAPIClient {
    static let shared = DriverAPIClient()
    
    private let session: URLSession
    private let baseURL: String
    
    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)
        self.baseURL = AppConfig.shared.baseURL
    }
    
    func request<T: Decodable>(
        _ endpoint: String,
        method: String = "GET",
        body: (any Encodable)? = nil,
        authenticated: Bool = true
    ) async throws -> T {
        guard let url = URL(string: baseURL + endpoint) else {
            throw APIError.invalidURL
        }
        
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if authenticated, let token = KeychainHelper.loadString(forKey: "authToken") {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body {
            req.httpBody = try JSONEncoder().encode(body)
        }
        
        let (data, response) = try await session.data(for: req)
        
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        switch http.statusCode {
        case 200...299:
            return try JSONDecoder().decode(T.self, from: data)
        case 401:
            throw APIError.unauthorized
        default:
            throw APIError.server("HTTP \(http.statusCode)")
        }
    }
}
```

**Why:** Actors provide compile-time guarantees against data races. URLSession is already thread-safe, but actor isolation prevents accidental mutation from multiple view models.

**Confidence:** HIGH — Based on [Swift URLSession async/await architecture](https://www.avanderlee.com/concurrency/urlsession-async-await-network-requests-in-swift/), [scalable networking layer](https://medium.com/@skrzypekpatryk/building-a-scalable-generic-networking-layer-using-async-await-in-swift-5926b94a5715).

### Pattern 2: @Observable for State Management (iOS 17+)
**What:** Use `@Observable` macro instead of `ObservableObject` + `@Published` for ViewModels and Managers.

**When:** All ViewModels, Managers, and root app state objects.

**Example:**
```swift
@Observable
final class AuthenticationManager {
    var isAuthenticated = false
    var currentUser: DriverUser?
    var isLoading = false
    var errorMessage: String?
    
    private let api = DriverAPIClient.shared
    
    func login(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await api.login(email: email, password: password)
            setAuthenticated(user: response.user, token: response.token)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

// In View:
struct LoginView: View {
    @State private var auth = AuthenticationManager()
    
    var body: some View {
        if auth.isLoading {
            ProgressView()
        }
    }
}
```

**Why:** 
- **Performance:** Views only re-render when specific properties they read change, not on any property change
- **Simpler syntax:** No `@Published`, no `@ObservedObject` / `@StateObject` confusion
- **Automatic observation:** All stored properties are observable by default

**Confidence:** HIGH — Based on [SwiftUI @Observable vs ObservableObject](https://www.donnywals.com/comparing-observable-to-observableobjects/), [Observable macro performance](https://www.avanderlee.com/swiftui/observable-macro-performance-increase-observableobject/).

### Pattern 3: Keychain for JWT Token Storage
**What:** Store authentication tokens in Keychain, never in UserDefaults or app storage.

**When:** All JWT tokens, refresh tokens, API keys.

**Example:**
```swift
struct KeychainHelper {
    static func save(_ string: String, forKey key: String) {
        let data = Data(string.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlocked
        ]
        
        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
    }
    
    static func loadString(forKey key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }
    
    static func delete(forKey key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }
}
```

**Security:** 
- Uses AES-256-GCM encryption with Secure Enclave protection
- `kSecAttrAccessibleWhenUnlocked` ensures tokens only available when device unlocked
- Survives app uninstall/reinstall (user must manually delete)

**Confidence:** HIGH — Based on [Keychain JWT storage best practices](https://capgo.app/blog/secure-token-storage-best-practices-for-mobile-developers/), [Keychain token security](https://medium.com/@ilginakgoz/using-keychain-how-to-securely-store-and-access-a-token-a0dc5bdf2d04).

### Pattern 4: Singleton Socket.IO Manager with @Observable
**What:** Single WebSocket connection per app lifecycle, exposing state via @Observable.

**When:** Real-time features (job alerts, live tracking, chat).

**Example:**
```swift
@Observable
final class SocketIOManager {
    static let shared = SocketIOManager()
    
    private var manager: SocketManager?
    private var socket: SocketIOClient?
    
    var isConnected = false
    var newJobAlert: DriverJob?
    var assignedJobId: String?
    
    private init() {}
    
    func connect(token: String) {
        let url = URL(string: AppConfig.shared.socketURL)!
        manager = SocketManager(socketURL: url, config: [
            .log(false),
            .compress,
            .connectParams(["token": token]),
            .forceWebsockets(true),
        ])
        
        socket = manager?.defaultSocket
        
        socket?.on(clientEvent: .connect) { [weak self] _, _ in
            self?.isConnected = true
        }
        
        socket?.on("job:new") { [weak self] data, _ in
            guard let dict = data.first as? [String: Any],
                  let jsonData = try? JSONSerialization.data(withJSONObject: dict),
                  let job = try? JSONDecoder().decode(DriverJob.self, from: jsonData) else { return }
            self?.newJobAlert = job
        }
        
        socket?.connect()
    }
    
    func emitLocation(lat: Double, lng: Double, contractorId: String?, jobId: String?) {
        var data: [String: Any] = ["lat": lat, "lng": lng]
        if let contractorId { data["contractor_id"] = contractorId }
        if let jobId { data["job_id"] = jobId }
        socket?.emit("driver:location", data)
    }
}
```

**Why:**
- **Single connection:** Avoid multiple WebSocket connections draining battery
- **Automatic reconnection:** Socket.IO handles reconnection logic
- **Observable state:** Views reactively update when `newJobAlert` changes
- **Token-based auth:** JWT passed as query param on connect

**Confidence:** MEDIUM — Based on [SwiftUI Socket.IO integration](https://medium.com/@ios_guru/swiftui-and-socket-io-ef036af3b57a), [Socket.IO Swift examples](https://github.com/projectnoa/SwiftUISocketSample). WebSearch-only source, but pattern verified in existing codebase.

### Pattern 5: Background Location Tracking with CoreLocation
**What:** Continuous GPS updates with background capability for driver app.

**When:** Driver app while online and accepting jobs.

**Example:**
```swift
@Observable
final class LocationManager: NSObject, CLLocationManagerDelegate {
    private let clManager = CLLocationManager()
    
    var currentLocation: CLLocation?
    var authorizationStatus: CLAuthorizationStatus = .notDetermined
    var isTracking = false
    var onLocationUpdate: ((CLLocation) -> Void)?
    
    override init() {
        super.init()
        clManager.delegate = self
        clManager.desiredAccuracy = kCLLocationAccuracyBest
        authorizationStatus = clManager.authorizationStatus
    }
    
    func startTracking() {
        guard !isTracking else { return }
        
        if clManager.authorizationStatus == .authorizedAlways {
            if Bundle.main.backgroundModes.contains("location") {
                clManager.allowsBackgroundLocationUpdates = true
                clManager.showsBackgroundLocationIndicator = true
            }
        }
        clManager.pausesLocationUpdatesAutomatically = false
        clManager.startUpdatingLocation()
        isTracking = true
    }
    
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        currentLocation = loc
        onLocationUpdate?(loc)
    }
}

// In AppState:
func startLocationTracking() {
    locationManager.startTracking()
    locationManager.onLocationUpdate = { [weak self] location in
        let lat = location.coordinate.latitude
        let lng = location.coordinate.longitude
        
        // Real-time via WebSocket
        self?.socket.emitLocation(lat: lat, lng: lng, 
                                  contractorId: self?.contractorProfile?.id,
                                  jobId: self?.activeJob?.id)
        
        // Persistence via REST (less frequent)
        Task {
            _ = try? await DriverAPIClient.shared.updateLocation(lat: lat, lng: lng)
        }
    }
}
```

**Required configuration:**
- **Info.plist:** `NSLocationWhenInUseUsageDescription`, `NSLocationAlwaysUsageDescription`
- **Capabilities:** Background Modes → Location updates
- **Permissions flow:** When in Use → Always (progressive disclosure)

**Confidence:** MEDIUM — Based on [iOS background location tracking](https://medium.com/@samermurad555/ios-background-processing-with-corelocation-97106943408c), [CoreLocation documentation](https://developer.apple.com/documentation/corelocation/handling-location-updates-in-the-background). Limited 2026-specific updates found.

### Pattern 6: Deep Linking with NavigationStack
**What:** Centralized URL routing for push notifications, universal links, widgets.

**When:** All deep link entry points (push tap, URL schemes, universal links).

**Example:**
```swift
enum DeepLink: Hashable {
    case job(id: String)
    case booking(id: String)
    case profile
}

@Observable
final class AppState {
    var navigationPath = NavigationPath()
    
    func handleDeepLink(_ userInfo: [AnyHashable: Any]) {
        if let jobId = userInfo["job_id"] as? String {
            navigationPath.append(DeepLink.job(id: jobId))
        } else if let bookingId = userInfo["booking_id"] as? String {
            navigationPath.append(DeepLink.booking(id: bookingId))
        }
    }
}

// In App:
struct DriverTabView: View {
    @State var appState: AppState
    
    var body: some View {
        NavigationStack(path: $appState.navigationPath) {
            TabView { /* tabs */ }
                .navigationDestination(for: DeepLink.self) { link in
                    switch link {
                    case .job(let id):
                        JobDetailView(jobId: id)
                    case .booking(let id):
                        BookingDetailView(bookingId: id)
                    case .profile:
                        ProfileView()
                    }
                }
        }
        .onReceive(NotificationCenter.default.publisher(for: .didTapPushNotification)) { notification in
            if let userInfo = notification.userInfo as? [AnyHashable: Any] {
                appState.handleDeepLink(userInfo)
            }
        }
    }
}
```

**Why:**
- **Single source of truth:** All navigation through one path
- **Testable:** Can programmatically trigger navigation
- **Resettable:** `path.removeLast()` or `path = NavigationPath()` to reset
- **Type-safe:** Enum-based routing prevents invalid states

**Confidence:** HIGH — Based on [SwiftUI deep linking](https://swiftwithmajid.com/2024/04/09/deep-linking-for-local-notifications-in-swiftui/), [push notification navigation](https://medium.com/@mohitsdhami8/swiftui-deep-linking-with-push-notifications-a-step-by-step-guide-aa2e8b1f03ce).

### Pattern 7: Stripe Payment Integration (Backend-Driven)
**What:** Create PaymentIntent on backend, confirm client-side with Apple Pay or card.

**When:** All payment flows (booking payments, tips, subscriptions).

**Example:**
```swift
class PaymentService {
    func createPaymentIntent(amountInDollars: Double, bookingId: String?) async throws -> PaymentIntentResponse {
        let requestBody = CreateIntentRequest(
            amount: amountInDollars,
            bookingId: bookingId,
            customerEmail: nil
        )
        
        let body = try JSONEncoder().encode(requestBody)
        // ... create URLRequest to POST /api/payments/create-intent-simple
        let (data, response) = try await session.data(for: request)
        return try JSONDecoder().decode(PaymentIntentResponse.self, from: data)
    }
    
    func presentApplePay(amount: Double, completion: @escaping (Result<String, Error>) -> Void) {
        let request = PKPaymentRequest()
        request.merchantIdentifier = "merchant.com.goumuve.app"
        request.supportedNetworks = [.visa, .masterCard, .amex, .discover]
        request.merchantCapabilities = .capability3DS
        request.countryCode = "US"
        request.currencyCode = "USD"
        request.paymentSummaryItems = [
            PKPaymentSummaryItem(label: "Umuve Pickup", amount: NSDecimalNumber(value: amount))
        ]
        
        guard let controller = PKPaymentAuthorizationViewController(paymentRequest: request) else {
            completion(.failure(PaymentError.applePayNotAvailable))
            return
        }
        
        // Present controller, handle authorization...
    }
}
```

**Backend endpoints:**
- `POST /api/payments/create-intent-simple` → Returns `clientSecret`, `paymentIntentId`
- `POST /api/payments/confirm-simple` → Confirms payment server-side

**Why:**
- **PCI compliance:** Card details never touch app/backend
- **Stripe handles complexity:** 3D Secure, SCA, retries
- **Apple Pay native:** PKPaymentAuthorizationViewController

**Confidence:** HIGH — Based on [Stripe iOS SDK](https://docs.stripe.com/sdks/ios), [SwiftUI Stripe integration](https://medium.com/geekculture/subscription-payment-using-stripe-ios-swiftui-sdk-409a9fdc1a0).

### Pattern 8: Push Notification Registration Flow
**What:** Request permission → Register with APNs → Send token to backend.

**When:** After user logs in and completes onboarding.

**Example:**
```swift
final class NotificationManager: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationManager()
    
    private(set) var isPermissionGranted = false
    
    func requestPermission() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .sound, .badge]
        ) { granted, error in
            DispatchQueue.main.async {
                self.isPermissionGranted = granted
                if granted {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
        }
    }
    
    func handleDeviceToken(_ deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        UserDefaults.standard.set(token, forKey: "pushDeviceToken")
        registerTokenWithBackend(token)
    }
    
    private func registerTokenWithBackend(_ token: String) {
        Task {
            do {
                _ = try await DriverAPIClient.shared.registerPushToken(token)
                UserDefaults.standard.set(true, forKey: "pushTokenRegistered")
            } catch {
                print("Token registration failed: \(error)")
            }
        }
    }
}

// In AppDelegate:
class DriverAppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        NotificationManager.shared.handleDeviceToken(deviceToken)
    }
}
```

**Backend endpoint:**
- `POST /api/push/register-token` with `{ token, platform: "ios", app_type: "driver" }`

**Why:**
- **Re-register after login:** Token must be associated with user account
- **Persist token:** Store in UserDefaults to re-send after auth
- **Handle failures gracefully:** Token registration can fail, retry later

**Confidence:** HIGH — Based on [iOS push notifications 2026 guide](https://medium.com/@khmannaict13/ios-push-notifications-the-complete-setup-guide-for-2026-adfc98592ab7), [APNs implementation](https://www.pushwoosh.com/blog/ios-push-notifications/).

## Anti-Patterns to Avoid

### Anti-Pattern 1: Networking in Views
**What:** Making API calls directly from SwiftUI views.

**Why bad:** 
- Violates separation of concerns
- Cannot unit test network logic
- Difficult to handle loading/error states consistently
- Leads to massive view files

**Instead:** 
- Views call ViewModel methods
- ViewModels orchestrate Service/APIClient calls
- Views only read ViewModel state properties

**Example of anti-pattern:**
```swift
// DON'T DO THIS
struct JobListView: View {
    @State private var jobs: [Job] = []
    
    var body: some View {
        List(jobs) { job in
            Text(job.address)
        }
        .task {
            // WRONG: API call in view
            let (data, _) = try! await URLSession.shared.data(from: URL(string: "https://api.com/jobs")!)
            jobs = try! JSONDecoder().decode([Job].self, from: data)
        }
    }
}
```

**Correct approach:**
```swift
@Observable
class JobListViewModel {
    var jobs: [Job] = []
    var isLoading = false
    var errorMessage: String?
    
    func loadJobs() async {
        isLoading = true
        do {
            jobs = try await DriverAPIClient.shared.getAvailableJobs().jobs
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct JobListView: View {
    @State private var viewModel = JobListViewModel()
    
    var body: some View {
        List(viewModel.jobs) { job in
            Text(job.address)
        }
        .task { await viewModel.loadJobs() }
    }
}
```

### Anti-Pattern 2: Using UserDefaults for Tokens
**What:** Storing JWT tokens in `UserDefaults` or `@AppStorage`.

**Why bad:**
- Unencrypted storage (accessible via iTunes backup)
- Can be extracted with file system access
- Not secure on jailbroken devices
- Violates security best practices

**Instead:** Always use Keychain with `kSecAttrAccessibleWhenUnlocked`.

### Anti-Pattern 3: Retain Cycles in Async Closures
**What:** Capturing `self` strongly in Socket.IO or location callbacks.

**Why bad:**
- Memory leaks preventing deallocation
- Managers/ViewModels never released
- Accumulates memory over time

**Example:**
```swift
// WRONG:
socket?.on("job:new") { data, _ in
    self.newJobAlert = parseJob(data) // Strong capture
}

// CORRECT:
socket?.on("job:new") { [weak self] data, _ in
    self?.newJobAlert = parseJob(data)
}
```

### Anti-Pattern 4: Fetching Details for Every List Item
**What:** Loading list, then making N API calls to get details for each item.

**Why bad:**
- Network waterfall (serial requests)
- Slow perceived performance
- Backend overload with 100+ requests

**Instead:** 
- Backend should include necessary details in list endpoint
- Use pagination to limit items per page
- Prefetch details for visible items only

**Confidence:** HIGH — Based on [iOS MVVM pitfalls](https://matteomanferdini.com/mvvm-pattern-ios-swift/), [architecture best practices](https://medium.com/@ishafajar11/building-a-robust-ios-networking-layer-with-mvvm-and-clean-architecture-testable-code-a-pokemon-48be7cb43dde).

### Anti-Pattern 5: ObservableObject After iOS 17
**What:** Using `ObservableObject` + `@Published` when targeting iOS 17+.

**Why bad:**
- Performance: Entire view re-renders on any property change
- Boilerplate: Requires `@Published` on every property
- Confusion: Mix of `@StateObject` and `@ObservedObject`

**Instead:** Use `@Observable` macro for all new code.

**Migration path:**
```swift
// OLD (ObservableObject):
class ViewModel: ObservableObject {
    @Published var isLoading = false
    @Published var data: [Item] = []
}
// In View: @StateObject var viewModel = ViewModel()

// NEW (@Observable):
@Observable
class ViewModel {
    var isLoading = false
    var data: [Item] = []
}
// In View: @State var viewModel = ViewModel()
```

**Confidence:** HIGH — Based on [@Observable migration guide](https://developer.apple.com/documentation/swiftui/migrating-from-the-observable-object-protocol-to-the-observable-macro), [performance comparison](https://www.avanderlee.com/swiftui/observable-macro-performance-increase-observableobject/).

### Anti-Pattern 6: Multiple WebSocket Connections
**What:** Creating new Socket.IO connection in every ViewModel.

**Why bad:**
- Battery drain from multiple TCP connections
- Duplicate event listeners
- Difficult to manage connection lifecycle
- Backend rate limiting

**Instead:** Singleton `SocketIOManager.shared` with single connection per app lifecycle.

### Anti-Pattern 7: Ignoring Background Location Battery Impact
**What:** Always-on background location without user-facing value.

**Why bad:**
- Drains battery (Apple rejects apps with unjustified usage)
- User trust issues ("Why is this app always tracking me?")
- Privacy concerns

**Instead:**
- Only track when driver is online and accepting jobs
- Show blue location indicator when tracking
- Provide clear UI toggle ("Go Online" → starts tracking)
- Stop immediately when going offline

**Required:** Background location usage description must justify why tracking is needed.

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| **API Rate Limiting** | Not needed | Implement exponential backoff in APIClient | Backend implements rate limits, client respects 429 responses |
| **Socket.IO Scaling** | Single server | Socket.IO sticky sessions with Redis adapter | Redis pub/sub for multi-node Socket.IO cluster |
| **Image Upload** | Base64 in JSON | Switch to multipart/form-data | Direct S3 upload with presigned URLs |
| **Offline Support** | None | Cache recent jobs/bookings in UserDefaults | SwiftData for local-first architecture with background sync |
| **Background Tasks** | None | Background fetch for pending job updates | BGTaskScheduler for silent job sync every 15 min |
| **Push Notification Targeting** | Broadcast to all drivers | Geofence-based targeting (send only to nearby drivers) | APNs topic filtering + backend geohash indexing |
| **Location Accuracy** | Best accuracy always | Adaptive accuracy (high when active job, low when idle) | Deferred updates API for batching location in background |
| **Memory Management** | No image caching | NSCache for loaded images | Image downsampling + progressive loading for large lists |

### Build Order Implications

**Phase 1: Foundation (Do First)**
- [ ] KeychainHelper utility
- [ ] APIClient actor with async/await
- [ ] AuthenticationManager with login/signup/Apple Sign In
- [ ] Basic models (User, Job, Booking, Codable structs)
- [ ] Config management (baseURL, API keys)

**Why first:** Everything depends on auth and networking. Cannot build features without data layer.

**Phase 2: Core Features**
- [ ] ViewModels for main screens (JobList, BookingFlow, Profile)
- [ ] NotificationManager setup
- [ ] PaymentService integration
- [ ] MapKit/CoreLocation integration
- [ ] SwiftUI Views and navigation

**Why second:** Depends on auth and API client. Delivers user-facing value.

**Phase 3: Real-Time Features**
- [ ] SocketIOManager setup
- [ ] Real-time job alerts (driver app)
- [ ] Live location streaming
- [ ] Push notification deep linking

**Why third:** Requires stable foundation. Real-time is complex and can be iterated on.

**Phase 4: Polish & Optimization**
- [ ] Offline caching (SwiftData or UserDefaults)
- [ ] Background task scheduling
- [ ] Image optimization and caching
- [ ] Error handling and retry logic
- [ ] Analytics and crash reporting

**Why last:** These are enhancements, not blockers for MVP.

### Dependency Graph

```
KeychainHelper → AuthManager → APIClient → ViewModels → Views
                      ↓
                NotificationManager → AppState → Views
                      
LocationManager → SocketIOManager → AppState → Views
                      ↑
                  APIClient (for token)

PaymentService → Stripe SDK + Backend API
      ↓
BookingViewModel → BookingFlow Views
```

**Critical path:** KeychainHelper → AuthManager → APIClient → First ViewModel

## Sources

### High Confidence (Official Docs + Context7)
- [Stripe iOS SDK Documentation](https://docs.stripe.com/sdks/ios)
- [Apple Developer: Migrating to @Observable](https://developer.apple.com/documentation/swiftui/migrating-from-the-observable-object-protocol-to-the-observable-macro)
- [Apple Developer: CoreLocation Background Updates](https://developer.apple.com/documentation/corelocation/handling-location-updates-in-the-background)

### Medium Confidence (Multiple WebSearch Sources)
- [URLSession with Async/Await - Antoine van der Lee](https://www.avanderlee.com/concurrency/urlsession-async-await-network-requests-in-swift/)
- [Building Scalable Networking Layer - Patryk Skrzypek](https://medium.com/@skrzypekpatryk/building-a-scalable-generic-networking-layer-using-async-await-in-swift-5926b94a5715)
- [@Observable Macro Performance - Antoine van der Lee](https://www.avanderlee.com/swiftui/observable-macro-performance-increase-observableobject/)
- [Comparing @Observable to ObservableObject - Donny Wals](https://www.donnywals.com/comparing-observable-to-observableobjects/)
- [Secure Token Storage Best Practices - Capgo](https://capgo.app/blog/secure-token-storage-best-practices-for-mobile-developers/)
- [Using Keychain for Token Storage - Ilgın Akgoz](https://medium.com/@ilginakgoz/using-keychain-how-to-securely-store-and-access-a-token-a0dc5bdf2d04)
- [SwiftUI Deep Linking with Push Notifications - Mohit Sharma](https://medium.com/@mohitsdhami8/swiftui-deep-linking-with-push-notifications-a-step-by-step-guide-aa2e8b1f03ce)
- [Deep Linking for Local Notifications - Swift with Majid](https://swiftwithmajid.com/2024/04/09/deep-linking-for-local-notifications-in-swiftui/)
- [iOS Push Notifications Guide 2026 - Khaled Hasan](https://medium.com/@khmannaict13/ios-push-notifications-the-complete-setup-guide-for-2026-adfc98592ab7)
- [iOS Push Notifications Best Practices - Pushwoosh](https://www.pushwoosh.com/blog/ios-push-notifications/)
- [MVVM in SwiftUI with Pitfalls - Matteo Manferdini](https://matteomanferdini.com/mvvm-pattern-ios-swift/)
- [iOS MVVM Clean Architecture - Ishafajar](https://medium.com/@ishafajar11/building-a-robust-ios-networking-layer-with-mvvm-and-clean-architecture-testable-code-a-pokemon-48be7cb43dde)

### Low Confidence (WebSearch Only - Verify in Phase)
- [SwiftUI and Socket.IO - iOS Guru](https://medium.com/@ios_guru/swiftui-and-socket-io-ef036af3b57a)
- [iOS Background Location - Samer Murad](https://medium.com/@samermurad555/ios-background-processing-with-corelocation-97106943408c)
- [Offline-First with SwiftData - Gaurav Harkhani](https://medium.com/@gauravharkhani01/designing-efficient-local-first-architectures-with-swiftdata-cc74048526f2)

### Existing Codebase Verification
- Customer App: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Clean/JunkOS/Services/APIClient.swift`
- Driver App: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Services/DriverAPIClient.swift`
- Socket Manager: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Services/SocketIOManager.swift`
- Auth Manager: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Managers/AuthenticationManager.swift`
- Location Manager: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Managers/LocationManager.swift`
- Notification Manager: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Managers/NotificationManager.swift`
- Payment Service: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Clean/JunkOS/Services/PaymentService.swift`

**Note:** Existing codebase already implements many of these patterns correctly. This research validates current approach and identifies areas for enhancement.
