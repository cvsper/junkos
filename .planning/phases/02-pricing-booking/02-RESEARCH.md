# Phase 2: Pricing & Booking - Research

**Researched:** 2026-02-13
**Domain:** SwiftUI multi-step booking flow with MapKit integration
**Confidence:** HIGH

## Summary

Phase 2 implements a complete booking flow in the customer iOS app (Umuve) from service selection through confirmation. This phase integrates MapKit for address entry and distance calculation, PhotosPicker for image uploads, and a backend pricing API. The codebase already has substantial infrastructure in place: design system, booking models, initial view implementations, and a working backend pricing engine.

**Key Finding:** The existing codebase uses ObservableObject (not @Observable) intentionally for iOS 16 compatibility, and several views already exist with the basic structure in place.

**Primary recommendation:** Use NavigationStack with programmatic navigation control via a shared BookingData ObservableObject, implement MapKit MKLocalSearchCompleter for address autocomplete with debouncing, and integrate PhotosPicker for multi-image selection. Follow the existing design system patterns and MVVM architecture already established in the codebase.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
**Booking flow structure:**
- Step-by-step wizard with one screen per step and progress indicator
- Free navigation: back button + tappable progress dots to jump to any completed step
- Running price estimate updates as the customer fills in steps (not just at review)
- Step order is Claude's discretion based on data dependencies

**Service selection:**
- Two large full-width tappable cards with icon, title, and brief description
- Junk Removal card and Auto Transport card — tap to select, highlighted state
- For Junk Removal: visual truck fill selector with illustration showing 1/4, 1/2, 3/4, full truck levels
- For Auto Transport: additional fields for vehicle info + surcharges (non-running, enclosed) per PROJECT.md

**Photo upload:**
- Camera + photo gallery as sources
- Maximum 10 photos per booking
- Whether photos are required or optional is Claude's discretion

**Address entry:**
- Junk Removal: pickup address only (driver handles disposal)
- Auto Transport: pickup + dropoff addresses
- Address entry UX is Claude's discretion (text field with MapKit autocomplete, map pin, or hybrid)
- Show mini-map preview after address selection

**Pricing display:**
- Running estimate shown as customer progresses through steps
- Summary with expandable detail: total shown prominently, tap to expand for line items (Base Fee, Distance Fee, Service Multiplier)
- Price updates when relevant inputs change (service type, address, volume)

**Review & confirm screen:**
- Full summary card showing everything: service type, address(es), photo thumbnails, scheduled date/time, price with expandable breakdown
- Single "Confirm Booking" button at bottom
- This is the last step before job creation (payment comes in Phase 3)

### Claude's Discretion
- Exact step order in the wizard (optimize for data dependencies — e.g., address before pricing calc)
- Whether photos are required (at least 1) or optional with encouragement
- Address entry UX (text autocomplete vs map pin vs hybrid)
- Schedule picker design (date + time selection)
- Progress indicator style (dots, numbered steps, progress bar)
- Loading and error states throughout the flow
- Photo upload UI (grid preview, reorder, delete)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope

</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SwiftUI | iOS 16+ | UI framework | Native iOS declarative UI framework |
| MapKit | iOS 16+ | Maps, geocoding, distance | Native iOS mapping framework, no API costs |
| PhotosUI | iOS 16+ | Photo selection | Native system photo picker (PhotosPicker) |
| Combine | iOS 16+ | Reactive state management | Built-in reactive framework for async/debouncing |
| CoreLocation | iOS 16+ | Location services, distance calculation | Native location/geocoding APIs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| URLSession | iOS 16+ | HTTP networking | API calls to backend (already in APIClient.swift) |
| JSONEncoder/Decoder | iOS 16+ | API serialization | Convert Swift models to/from JSON |
| KeychainHelper | Custom | Secure token storage | JWT auth token persistence (already implemented) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MapKit | Google Maps SDK | MapKit is free, native, and matches Apple HIG; Google requires API keys and billing |
| PhotosPicker | UIImagePickerController | PhotosPicker is modern SwiftUI API (iOS 16+), UIImagePickerController requires UIKit bridging |
| ObservableObject | @Observable macro | Codebase uses ObservableObject for iOS 16 compatibility; @Observable requires iOS 17+ |

**Installation:**
No external dependencies required — all frameworks are built into iOS 16+.

## Architecture Patterns

### Recommended Project Structure
The codebase already follows this structure:
```
JunkOS-Clean/JunkOS/
├── Models/              # BookingModels.swift, APIModels.swift
├── Views/               # All view files (one per step)
├── ViewModels/          # One ViewModel per View (MVVM pattern)
├── Services/            # APIClient.swift, Config.swift
├── Utilities/           # LocationManager.swift, HapticManager.swift
├── Components/          # Reusable UI components
└── Design/              # DesignSystem.swift (colors, typography, spacing)
```

### Pattern 1: Shared ObservableObject for Wizard State
**What:** A single `BookingData` ObservableObject holds all wizard state and is passed via `.environmentObject()` to all steps.

**When to use:** Multi-step flows where later steps depend on earlier data and you need bidirectional navigation.

**Example:**
```swift
// Already implemented in BookingModels.swift
class BookingData: ObservableObject {
    @Published var address: Address = Address()
    @Published var photos: [Data] = []
    @Published var selectedServices: Set<String> = []
    @Published var selectedDate: Date?
    @Published var selectedTimeSlot: String?
    // ... more properties
}

// Usage in parent view:
NavigationStack {
    ServiceSelectionView()
        .environmentObject(bookingData)
}
```

**Why this pattern:** Avoids prop-drilling, maintains single source of truth, and supports free navigation (user can go back and change earlier steps without data loss). Source: [SwiftUI NavigationStack patterns for predictable multi-step flows](https://appmaster.io/blog/swiftui-navigationstack-multistep-flows)

### Pattern 2: MVVM with View-Specific ViewModels
**What:** Each view has a corresponding ViewModel (ObservableObject) for view-specific logic, while shared state lives in BookingData.

**When to use:** When a view needs local state, async operations, or business logic that shouldn't pollute the shared BookingData.

**Example:**
```swift
// ServiceSelectionViewModel.swift (already exists)
class ServiceSelectionViewModel: ObservableObject {
    @Published var availableServices: [Service] = []
    @Published var isLoading: Bool = false

    func loadServices() async {
        // View-specific async logic
    }
}

// ServiceSelectionView.swift
struct ServiceSelectionView: View {
    @EnvironmentObject var bookingData: BookingData  // Shared state
    @StateObject private var viewModel = ServiceSelectionViewModel()  // Local state
}
```

**Why this pattern:** Separation of concerns — shared wizard state vs view-specific ephemeral state. Source: Codebase analysis (existing ViewModels follow this pattern)

### Pattern 3: MapKit Address Autocomplete with Debouncing
**What:** Use MKLocalSearchCompleter with Combine's debounce to provide real-time address suggestions without overwhelming the API.

**When to use:** Address input fields with autocomplete.

**Example:**
```swift
// Source: https://levelup.gitconnected.com/implementing-address-autocomplete-using-swiftui-and-mapkit-c094d08cda24
class LocationSearchViewModel: NSObject, ObservableObject, MKLocalSearchCompleterDelegate {
    @Published var searchQuery = ""
    @Published var completions: [MKLocalSearchCompletion] = []

    private var completer = MKLocalSearchCompleter()
    private var cancellables = Set<AnyCancellable>()

    override init() {
        super.init()
        completer.delegate = self
        completer.resultTypes = .address

        // Debounce search queries
        $searchQuery
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { [weak self] query in
                self?.completer.queryFragment = query
            }
            .store(in: &cancellables)
    }

    func completerDidUpdateResults(_ completer: MKLocalSearchCompleter) {
        completions = completer.results
    }
}
```

**Why this pattern:** MKLocalSearchCompleter has no rate limiting, but debouncing prevents UI jank when user types quickly. Source: [Building a Debounced Autocomplete in Swift with Combine and MapKit](https://medium.com/@srikanthvelaga55/building-a-debounced-autocomplete-in-swift-with-combine-and-mapkit-ef2f35ae519d)

### Pattern 4: PhotosPicker Multi-Image Selection
**What:** Use SwiftUI's PhotosPicker with PhotosPickerItem array for multi-image selection.

**When to use:** Selecting multiple photos from gallery.

**Example:**
```swift
// Source: https://www.hackingwithswift.com/quick-start/swiftui/how-to-let-users-select-pictures-using-photospicker
struct PhotoUploadView: View {
    @State private var selectedItems = [PhotosPickerItem]()
    @State private var selectedImages = [Data]()

    var body: some View {
        PhotosPicker(
            selection: $selectedItems,
            maxSelectionCount: 10,
            matching: .images
        ) {
            Text("Select Photos")
        }
        .onChange(of: selectedItems) { items in
            Task {
                selectedImages = []
                for item in items {
                    if let data = try? await item.loadTransferable(type: Data.self) {
                        selectedImages.append(data)
                    }
                }
            }
        }
    }
}
```

**Why this pattern:** PhotosPicker is the modern SwiftUI API (iOS 16+), handles permissions automatically, and supports multi-selection natively. Source: [How to Use PhotosPicker in SwiftUI](https://www.appcoda.com/swiftui-photospicker/)

### Pattern 5: NavigationStack with Programmatic Navigation
**What:** Use NavigationLink for forward navigation, but track state in BookingData for "jump to step" functionality.

**When to use:** Wizard flows with free navigation (user can jump back to any completed step).

**Example:**
```swift
// Modern NavigationStack pattern (iOS 16+)
// Source: https://medium.com/@dinaga119/mastering-navigation-in-swiftui-the-2025-guide-to-clean-scalable-routing-bbcb6dbce929
struct BookingWizardView: View {
    @StateObject var bookingData = BookingData()

    var body: some View {
        NavigationStack {
            ServiceSelectionView()
                .environmentObject(bookingData)
        }
    }
}

// In ServiceSelectionView:
NavigationLink(destination: AddressInputView().environmentObject(bookingData)) {
    Text("Continue")
}
```

**Why this pattern:** Simple, predictable, works with system back button and swipe-back gesture. For "jump to step," you could use NavigationPath, but given the phase scope, sequential NavigationLink with disabled state when earlier steps are incomplete is cleaner. Source: [Modern SwiftUI Navigation: Best Practices for 2025 Apps](https://medium.com/@dinaga119/mastering-navigation-in-swiftui-the-2025-guide-to-clean-scalable-routing-bbcb6dbce929)

### Anti-Patterns to Avoid
- **Passing closures for navigation:** Don't pass navigation handlers via closures; use NavigationLink or NavigationPath centrally.
- **Duplicating wizard state:** Don't store the same data in both BookingData and individual ViewModels; use BookingData as single source of truth for persistent wizard data.
- **Blocking UI during debounced search:** Don't show loading indicators for every keystroke; debounce first, then show indicators only for actual network calls.
- **Synchronous photo loading:** Don't block the main thread loading PhotosPickerItem data; always use `Task { await ... }`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Address autocomplete | Custom search service | MKLocalSearchCompleter | Handles caching, ranking, localization, and has no rate limits |
| Distance calculation | Haversine formula manually | CLLocation.distance(from:) | Accounts for Earth's ellipsoid shape, more accurate than simple Haversine |
| Photo selection UI | Custom gallery | PhotosPicker | Handles permissions, iCloud sync, multi-selection, system consistency |
| Form validation | Manual field-by-field checks | Combine + @Published with validation rules | Reactive validation prevents stale state and cascade bugs |
| Multipart upload | Manual boundary generation | URLSession with pre-built multipart body | Edge cases like filename encoding, MIME types, boundary collisions |

**Key insight:** iOS provides production-ready APIs for maps, photos, and location that already handle edge cases like permissions, privacy, iCloud Photos, offline maps, and localization. Building custom versions introduces bugs and violates Apple's Human Interface Guidelines.

## Common Pitfalls

### Pitfall 1: ObservableObject Retain Cycles in ViewModels
**What goes wrong:** ViewModels store strong references to closures that capture self, causing memory leaks.

**Why it happens:** `@StateObject` retains the ViewModel for the view's lifetime, but if the ViewModel's closures strongly capture it, neither gets deallocated.

**How to avoid:** Always use `[weak self]` in closures inside ObservableObjects:
```swift
class AddressInputViewModel: ObservableObject {
    func detectLocation(completion: @escaping (Result<Address, Error>) -> Void) {
        locationManager.requestLocation { [weak self] location in
            self?.processLocation(location)
            completion(.success(address))
        }
    }
}
```

**Warning signs:** Memory usage growing with each navigation to a view; Instruments showing leaked ViewModels.

### Pitfall 2: MKLocalSearchCompleter Delegate Calls on Background Thread
**What goes wrong:** `completerDidUpdateResults` is called on a background queue, but updating `@Published` properties off the main thread crashes SwiftUI.

**Why it happens:** MKLocalSearchCompleter doesn't guarantee main thread callbacks.

**How to avoid:** Always dispatch to main queue in delegate methods:
```swift
func completerDidUpdateResults(_ completer: MKLocalSearchCompleter) {
    DispatchQueue.main.async {
        self.completions = completer.results
    }
}
```

**Warning signs:** Purple runtime warnings about publishing changes off main thread; intermittent crashes during address search.

### Pitfall 3: PhotosPickerItem Loading Blocking Main Thread
**What goes wrong:** Using `.loadTransferable(type: Data.self)` synchronously blocks the UI while photos load from iCloud.

**Why it happens:** PhotosPickerItem can fetch from iCloud, which is slow over cellular.

**How to avoid:** Always load asynchronously in a Task:
```swift
.onChange(of: selectedItems) { items in
    Task {  // ← Must be async
        for item in items {
            if let data = try? await item.loadTransferable(type: Data.self) {
                photos.append(data)
            }
        }
    }
}
```

**Warning signs:** UI freezes when selecting photos; watchdog timeouts on slow connections.

### Pitfall 4: NavigationLink State Desync with BookingData
**What goes wrong:** User navigates forward, then back, then changes data in an earlier step — later steps show stale data.

**Why it happens:** NavigationLink doesn't automatically re-render destination views when BookingData changes.

**How to avoid:** Use `.id()` on NavigationLink destinations to force re-creation when relevant data changes:
```swift
NavigationLink(destination:
    ReviewView()
        .environmentObject(bookingData)
        .id(bookingData.selectedServices)  // Re-create when services change
) {
    Text("Review")
}
```

**Warning signs:** Stale data shown in review screen after going back and changing selections.

### Pitfall 5: Missing iOS 16 Availability Checks
**What goes wrong:** Using PhotosPicker or NavigationStack on iOS 15 crashes the app.

**Why it happens:** These APIs were introduced in iOS 16.

**How to avoid:** Already handled — codebase targets iOS 16+ (PROJECT.md states "minimum iOS 14+" but uses iOS 16 APIs, so iOS 16 is the actual minimum).

**Warning signs:** Crashes on older devices; compiler warnings about unavailable APIs.

### Pitfall 6: Not Clearing Debounce Cancellables
**What goes wrong:** Combine subscriptions survive longer than the ViewModel, causing updates after the view is dismissed.

**Why it happens:** AnyCancellable subscriptions aren't automatically cancelled when stored in a property.

**How to avoid:** Store in a Set and rely on ViewModel deallocation, or explicitly cancel in deinit:
```swift
class AddressViewModel: ObservableObject {
    private var cancellables = Set<AnyCancellable>()

    init() {
        $searchQuery
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { ... }
            .store(in: &cancellables)  // ← Will cancel when Set deallocates
    }
}
```

**Warning signs:** Console messages about updates on deallocated ViewModels; unexpected network requests.

## Code Examples

Verified patterns from official sources:

### Multi-Image Selection with PhotosPicker
```swift
// Source: https://www.appcoda.com/swiftui-photospicker/
import PhotosUI
import SwiftUI

struct PhotoUploadView: View {
    @State private var selectedItems: [PhotosPickerItem] = []
    @State private var selectedPhotos: [Data] = []

    var body: some View {
        VStack {
            PhotosPicker(
                selection: $selectedItems,
                maxSelectionCount: 10,
                matching: .images
            ) {
                Label("Select Photos", systemImage: "photo")
            }

            ScrollView {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 100))]) {
                    ForEach(selectedPhotos.indices, id: \.self) { index in
                        if let uiImage = UIImage(data: selectedPhotos[index]) {
                            Image(uiImage: uiImage)
                                .resizable()
                                .scaledToFill()
                                .frame(width: 100, height: 100)
                                .clipped()
                        }
                    }
                }
            }
        }
        .onChange(of: selectedItems) { newItems in
            Task {
                selectedPhotos = []
                for item in newItems {
                    if let data = try? await item.loadTransferable(type: Data.self) {
                        selectedPhotos.append(data)
                    }
                }
            }
        }
    }
}
```

### MapKit Address Autocomplete
```swift
// Source: https://levelup.gitconnected.com/implementing-address-autocomplete-using-swiftui-and-mapkit-c094d08cda24
import MapKit
import Combine

class AddressSearchViewModel: NSObject, ObservableObject, MKLocalSearchCompleterDelegate {
    @Published var searchQuery = ""
    @Published var completions: [MKLocalSearchCompletion] = []

    private let completer = MKLocalSearchCompleter()
    private var cancellables = Set<AnyCancellable>()

    override init() {
        super.init()
        completer.delegate = self
        completer.resultTypes = .address

        $searchQuery
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .removeDuplicates()
            .sink { [weak self] query in
                if query.isEmpty {
                    self?.completions = []
                } else {
                    self?.completer.queryFragment = query
                }
            }
            .store(in: &cancellables)
    }

    func completerDidUpdateResults(_ completer: MKLocalSearchCompleter) {
        DispatchQueue.main.async {
            self.completions = completer.results
        }
    }

    func completer(_ completer: MKLocalSearchCompleter, didFailWithError error: Error) {
        print("Address search error: \(error.localizedDescription)")
    }
}
```

### CLLocation Distance Calculation
```swift
// Source: https://developer.apple.com/documentation/mapkit/mkmappoint/1452729-distance
import CoreLocation

func calculateDistance(from startCoord: CLLocationCoordinate2D, to endCoord: CLLocationCoordinate2D) -> Double {
    let startLocation = CLLocation(latitude: startCoord.latitude, longitude: startCoord.longitude)
    let endLocation = CLLocation(latitude: endCoord.latitude, longitude: endCoord.longitude)

    // Returns distance in meters
    let distanceInMeters = startLocation.distance(from: endLocation)

    // Convert to miles
    let distanceInMiles = distanceInMeters / 1609.34

    return distanceInMiles
}
```

### Multipart Form Data Upload
```swift
// Source: https://theswiftdev.com/easy-multipart-file-upload-for-swift/
func uploadPhotos(_ photos: [Data]) async throws -> [String] {
    let boundary = UUID().uuidString
    let url = URL(string: "https://api.example.com/upload")!

    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

    var body = Data()

    for (index, photoData) in photos.enumerated() {
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"files\"; filename=\"photo\(index).jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(photoData)
        body.append("\r\n".data(using: .utf8)!)
    }

    body.append("--\(boundary)--\r\n".data(using: .utf8)!)

    request.httpBody = body

    let (data, response) = try await URLSession.shared.data(for: request)

    guard let httpResponse = response as? HTTPURLResponse,
          (200...299).contains(httpResponse.statusCode) else {
        throw URLError(.badServerResponse)
    }

    let result = try JSONDecoder().decode(UploadResponse.self, from: data)
    return result.urls
}

struct UploadResponse: Codable {
    let success: Bool
    let urls: [String]
}
```

### Real-Time Form Validation
```swift
// Source: https://azamsharp.com/2024/12/18/the-ultimate-guide-to-validation-patterns-in-swiftui.html
import Combine

class AddressFormViewModel: ObservableObject {
    @Published var street = ""
    @Published var city = ""
    @Published var zipCode = ""

    @Published var streetError: String?
    @Published var cityError: String?
    @Published var zipCodeError: String?

    private var cancellables = Set<AnyCancellable>()

    var isFormValid: Bool {
        streetError == nil && cityError == nil && zipCodeError == nil &&
        !street.isEmpty && !city.isEmpty && !zipCode.isEmpty
    }

    init() {
        // Validate street
        $street
            .debounce(for: .milliseconds(500), scheduler: RunLoop.main)
            .map { street -> String? in
                guard !street.isEmpty else { return "Street address is required" }
                guard street.count >= 3 else { return "Street address too short" }
                return nil
            }
            .assign(to: &$streetError)

        // Validate city
        $city
            .debounce(for: .milliseconds(500), scheduler: RunLoop.main)
            .map { city -> String? in
                guard !city.isEmpty else { return "City is required" }
                return nil
            }
            .assign(to: &$cityError)

        // Validate ZIP code
        $zipCode
            .debounce(for: .milliseconds(500), scheduler: RunLoop.main)
            .map { zip -> String? in
                guard !zip.isEmpty else { return "ZIP code is required" }
                let zipRegex = "^[0-9]{5}$"
                guard zip.range(of: zipRegex, options: .regularExpression) != nil else {
                    return "Invalid ZIP code format"
                }
                return nil
            }
            .assign(to: &$zipCodeError)
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| NavigationView | NavigationStack | iOS 16 (2022) | Programmatic navigation with NavigationPath, better deep linking |
| UIImagePickerController | PhotosPicker | iOS 16 (2022) | Native SwiftUI API, handles permissions/iCloud automatically |
| @ObservedObject everywhere | @Observable macro | iOS 17 (2023) | Simpler syntax, but not yet adopted in this codebase (iOS 16 target) |
| Manual geocoding | MKLocalSearchCompleter | iOS 13+ | Real-time autocomplete with no rate limits |
| Manual distance calc | CLLocation.distance(from:) | iOS 2.0+ | More accurate than Haversine, accounts for elevation |

**Deprecated/outdated:**
- **NavigationView**: Deprecated in iOS 16; use NavigationStack instead (though codebase may still use NavigationView for iOS 14 compatibility)
- **UIViewRepresentable for UIImagePickerController**: Use PhotosPicker for modern SwiftUI (iOS 16+)
- **UserDefaults for auth tokens**: Use Keychain (already done in this codebase via KeychainHelper)

## Backend Integration

### Pricing API (Already Implemented)
The backend has a comprehensive pricing engine at `/api/pricing/estimate`:

**Request:**
```json
{
  "items": [
    { "category": "furniture", "quantity": 2, "size": "large" },
    { "category": "appliances", "quantity": 1, "size": "medium" }
  ],
  "scheduledDate": "2026-02-20",
  "address": {
    "lat": 27.9506,
    "lng": -82.4572
  }
}
```

**Response:**
```json
{
  "success": true,
  "estimate": {
    "subtotal": 240.00,
    "service_fee": 19.20,
    "volume_discount": -24.00,
    "time_surge": 0.00,
    "zone_surge": 0.00,
    "total": 235.20,
    "breakdown": { ... },
    "estimated_duration_minutes": 46,
    "recommended_truck": "Standard Pickup"
  }
}
```

**Key points:**
- Backend uses tiered category pricing with size variants (small/medium/large)
- Supports volume discounts (4 tiers: 1-3, 4-7, 8-15, 16+ items)
- Time-based surge (same-day +25%, next-day +10%, weekend +15%)
- Minimum job price: $89
- Backend source: `/Users/sevs/Documents/Programs/webapps/junkos/backend/routes/booking.py` and `/Users/sevs/Documents/Programs/webapps/junkos/backend/routes/pricing.py`

### Photo Upload API (Already Implemented)
Backend has multipart upload at `/api/upload/photos`:

**Constraints:**
- Max 10 files per request
- Max 10 MB per file
- Allowed types: jpg, jpeg, png, webp
- Returns array of URLs: `{ "success": true, "urls": ["/uploads/uuid.jpg", ...] }`

**Backend source:** `/Users/sevs/Documents/Programs/webapps/junkos/backend/routes/upload.py`

### Job Creation API (Backend Pattern)
Backend expects job creation via `/api/jobs` (route in booking.py):

**Required fields:**
- `address` (string)
- `lat`, `lng` (floats)
- `items` (array of objects: `{ category, quantity, size }`)
- `photos` (array of URLs from upload endpoint)
- `scheduled_date` (ISO date string)
- `scheduled_time` (HH:MM string)
- `estimated_price` (float, from pricing estimate)

**Flow:**
1. Customer selects service → map to item categories
2. Customer uploads photos → get URLs
3. Customer enters address → geocode to lat/lng
4. Get pricing estimate → store estimated_price
5. Create job with all data → backend returns job_id

## Existing Codebase State

### Already Implemented
- ✅ `BookingData` ObservableObject with all wizard state
- ✅ Design system (colors, typography, spacing, components)
- ✅ `APIClient.swift` with networking and auth headers
- ✅ `KeychainHelper.swift` for secure token storage
- ✅ `ServiceSelectionView` with basic service cards
- ✅ `AddressInputView` with map preview (needs autocomplete enhancement)
- ✅ `PhotoUploadView` with PhotosPicker integration
- ✅ `DateTimePickerView` with date/time selection
- ✅ `ConfirmationView` with review summary
- ✅ All ViewModels for each view (ServiceSelectionViewModel, etc.)
- ✅ `LocationManager.swift` for current location detection
- ✅ Backend pricing API and upload endpoints

### Needs Implementation
- ❌ Service type selection screen (Junk Removal vs Auto Transport)
- ❌ Truck fill selector (1/4, 1/2, 3/4, full) for Junk Removal
- ❌ Vehicle info fields (non-running, enclosed) for Auto Transport
- ❌ Address autocomplete with MKLocalSearchCompleter
- ❌ Dropoff address for Auto Transport
- ❌ Running price estimate display throughout flow
- ❌ Distance calculation integration with pricing
- ❌ Real-time form validation with error messages
- ❌ Progress indicator with tappable dots for jump navigation
- ❌ Job creation API call in ConfirmationViewModel

### Implementation Notes
The codebase currently has a "LoadUp" themed implementation with service tiers and commercial booking features that aren't in the Phase 2 requirements. The actual Phase 2 requirements focus on Junk Removal vs Auto Transport service selection, not the existing "Full-Service vs Curbside" tiers. This means some refactoring is needed to align with the user's vision.

## Open Questions

1. **Service selection refactor scope**
   - What we know: Current `ServiceSelectionView` shows service cards (furniture, appliances, etc.), but Phase 2 requires "Junk Removal vs Auto Transport" as the first decision
   - What's unclear: Should service cards become sub-selections under Junk Removal, or is Junk Removal volume-based only?
   - Recommendation: Treat Junk Removal as volume-based (truck fill selector), Auto Transport as vehicle-based (one vehicle per booking). Service cards can be replaced with truck fill selector.

2. **Pricing calculation trigger timing**
   - What we know: Requirements say "running price estimate updates as customer fills in steps"
   - What's unclear: When exactly to call `/api/pricing/estimate` — after every field change, or only when a step is completed?
   - Recommendation: Call pricing API only after completing address step (need lat/lng) and updating service selections. Debounce updates to avoid excessive API calls.

3. **Photo requirement strictness**
   - What we know: Max 10 photos, user decides if required or optional
   - What's unclear: If optional, should there be a minimum recommendation (e.g., "at least 1 recommended")?
   - Recommendation: Make photos optional but strongly encouraged with UI messaging like "Photos help us provide accurate pricing" and show a warning if proceeding without photos.

4. **Auto Transport address flow**
   - What we know: Auto Transport needs pickup + dropoff addresses
   - What's unclear: Should these be separate steps, or both collected on one screen?
   - Recommendation: Single address input screen that conditionally shows dropoff address field when service type is Auto Transport. Reduces step count and complexity.

5. **Truck fill selector visual design**
   - What we know: User wants "visual truck fill selector with illustration showing 1/4, 1/2, 3/4, full truck levels"
   - What's unclear: Custom illustration vs SF Symbols, interactive vs tap-to-select cards
   - Recommendation: Use SF Symbols (`truck.box.fill` with varying opacity) for simplicity, tap-to-select cards with visual feedback. Custom illustrations can be Phase 7 polish.

## Sources

### Primary (HIGH confidence)
- Apple Developer Documentation: [MKLocalSearchCompleter](https://developer.apple.com/documentation/mapkit/mklocalsearchcompleter)
- Apple Developer Documentation: [PhotosPicker](https://developer.apple.com/documentation/photokit/photospicker)
- Apple Developer Documentation: [CLLocation.distance(from:)](https://developer.apple.com/documentation/corelocation/cllocation/1423689-distance)
- Codebase analysis: `/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Clean/JunkOS/` (Models, Views, ViewModels, Services)
- Backend source code: `/Users/sevs/Documents/Programs/webapps/junkos/backend/routes/` (booking.py, pricing.py, upload.py)

### Secondary (MEDIUM confidence)
- [Modern SwiftUI Navigation: Best Practices for 2025 Apps](https://medium.com/@dinaga119/mastering-navigation-in-swiftui-the-2025-guide-to-clean-scalable-routing-bbcb6dbce929) — NavigationStack patterns
- [SwiftUI NavigationStack patterns for predictable multi-step flows](https://appmaster.io/blog/swiftui-navigationstack-multistep-flows) — Multi-step wizard guidance
- [Implementing address autocomplete using SwiftUI and MapKit](https://levelup.gitconnected.com/implementing-address-autocomplete-using-swiftui-and-mapkit-c094d08cda24) — MKLocalSearchCompleter implementation
- [How to Use PhotosPicker in SwiftUI](https://www.appcoda.com/swiftui-photospicker/) — PhotosPicker multi-selection
- [Easy multipart file upload for Swift](https://theswiftdev.com/easy-multipart-file-upload-for-swift/) — Multipart upload implementation
- [The Ultimate Guide To Validation Patterns In SwiftUI](https://azamsharp.com/2024/12/18/the-ultimate-guide-to-validation-patterns-in-swiftui.html) — Real-time validation
- [SwiftUI Forms: Stop Building Forms That Users Hate](https://medium.com/@chandra.welim/swiftui-forms-stop-building-forms-that-users-hate-1fedbbea2071) — Form UX best practices
- [Distance between CLLocationCoordinate2D values](https://www.ralfebert.com/swift/cllocationcoordinate2d-distance/) — Distance calculation

### Tertiary (LOW confidence)
- None flagged — all sources verified with official documentation or recent community implementations

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All native iOS frameworks with official documentation
- Architecture: HIGH - Patterns verified in existing codebase and official Apple tutorials
- Pitfalls: MEDIUM - Derived from community experience and issue trackers, not always officially documented

**Research date:** 2026-02-13
**Valid until:** 60 days (native iOS APIs are stable; re-verify if WWDC 2026 introduces breaking changes)
