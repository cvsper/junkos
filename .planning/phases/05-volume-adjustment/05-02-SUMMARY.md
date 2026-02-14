---
phase: 05-volume-adjustment
plan: 02
subsystem: driver-ios
tags: [volume-adjustment, swiftui, socket-io, combine, real-time]
dependency_graph:
  requires:
    - Phase 5-01 volume adjustment backend endpoints
    - Phase 4 Socket.IO NotificationCenter bridge pattern
    - Phase 4 DriverAPIClient async/await pattern
  provides:
    - VolumeAdjustmentView for driver volume input
    - VolumeAdjustmentViewModel with Socket.IO listeners
    - Navigation from ActiveJobView to volume adjustment
    - Auto-approve, waiting, approve, and decline UI states
  affects:
    - ActiveJobView (added "Adjust Volume" button for arrived status)
    - SocketIOManager (volume:approved and volume:declined listeners)
tech_stack:
  added:
    - Combine framework for NotificationCenter publishers
  patterns:
    - NotificationCenter bridge for Socket.IO events (from Phase 4)
    - @Observable pattern for SwiftUI state management
    - Decimal keyboard with input filtering (digits and single decimal point)
    - Overlay-based status UI (waiting, approved, declined)
    - NavigationLink from ActiveJobView to detail screen
key_files:
  created:
    - JunkOS-Driver/ViewModels/VolumeAdjustmentViewModel.swift
    - JunkOS-Driver/Views/ActiveJob/VolumeAdjustmentView.swift
  modified:
    - JunkOS-Driver/Services/DriverAPIClient.swift (proposeVolumeAdjustment method)
    - JunkOS-Driver/Services/SocketIOManager.swift (volume:approved and volume:declined listeners)
    - JunkOS-Driver/Models/JobModels.swift (VolumeProposalResponse model)
    - JunkOS-Driver/Views/ActiveJob/ActiveJobView.swift (navigation to VolumeAdjustmentView)
decisions:
  - Decimal keyboard with filter allowing only digits and single decimal point (max 1 decimal place)
  - NotificationCenter bridge pattern for Socket.IO events (consistent with Phase 4 job feed pattern)
  - Auto-approve shows immediate success overlay without waiting spinner
  - Decline overlay shows trip fee amount from Socket.IO payload
  - Price comparison card shows original → new price with color coding (green for decrease, red for increase)
  - "Adjust Volume" button appears below BeforePhotosView in arrived status (non-blocking, optional action)
metrics:
  duration_minutes: 2.75
  tasks_completed: 2
  commits: 2
  files_created: 2
  files_modified: 4
  completed_date: 2026-02-14
---

# Phase 5 Plan 2: Driver Volume Adjustment UI Summary

Driver iOS volume adjustment UI complete: VolumeAdjustmentView with decimal input, price preview, API call, and real-time Socket.IO approval/decline response handling.

## One-liner

Driver volume adjustment UI with decimal input, price comparison, Socket.IO listeners for real-time customer approval/decline response, and status overlays for auto-approve, waiting, approve, and decline states.

## What Was Built

### VolumeAdjustmentViewModel

**File:** `JunkOS-Driver/ViewModels/VolumeAdjustmentViewModel.swift`

**Properties:**
- `volumeInput: String` — raw text input for volume (decimal)
- `isSubmitting: Bool` — loading state during API call
- `isWaitingForApproval: Bool` — true when waiting for customer response (price increase)
- `wasApproved: Bool?` — nil = pending, true = approved, false = declined
- `autoApproved: Bool` — true when price decreased and was auto-approved
- `newPrice: Double?` — calculated new price from API
- `originalPrice: Double?` — original price for comparison
- `errorMessage: String?` — API error display
- `tripFee: Double?` — trip fee amount from decline Socket.IO event

**Socket.IO Listeners (via NotificationCenter):**
```swift
NotificationCenter.default.publisher(for: NSNotification.Name("socket:volume:approved"))
    .receive(on: RunLoop.main)
    .sink { [weak self] _ in
        self?.wasApproved = true
        self?.isWaitingForApproval = false
        HapticManager.shared.success()
    }
    .store(in: &cancellables)

NotificationCenter.default.publisher(for: NSNotification.Name("socket:volume:declined"))
    .receive(on: RunLoop.main)
    .sink { [weak self] notification in
        self?.wasApproved = false
        self?.isWaitingForApproval = false
        self?.tripFee = (notification.userInfo?["trip_fee"] as? NSNumber)?.doubleValue ?? 50.0
        HapticManager.shared.error()
    }
    .store(in: &cancellables)
```

**Computed Properties:**
- `parsedVolume: Double?` — converts volumeInput string to Double
- `isValid: Bool` — true if parsedVolume exists and > 0

**API Method:**
```swift
func proposeAdjustment(jobId: String) async {
    guard isValid else { return }
    isSubmitting = true
    errorMessage = nil

    do {
        let response = try await api.proposeVolumeAdjustment(jobId: jobId, actualVolume: parsedVolume!)
        newPrice = response.newPrice
        originalPrice = response.originalPrice

        if response.autoApproved == true {
            // Price decreased - auto-approved
            autoApproved = true
            wasApproved = true
            HapticManager.shared.success()
        } else {
            // Price increased - waiting for customer approval
            isWaitingForApproval = true
        }
    } catch {
        errorMessage = error.localizedDescription
        HapticManager.shared.error()
    }

    isSubmitting = false
}
```

### VolumeAdjustmentView

**File:** `JunkOS-Driver/Views/ActiveJob/VolumeAdjustmentView.swift`

**UI Sections:**

1. **Header:** "Adjust Volume" title + subtitle
2. **Original Estimate Card:** Displays `job.volumeEstimate` if available
3. **Volume Input Field:**
   - TextField with `.keyboardType(.decimalPad)`
   - `onChange` filter: allows only digits and single decimal point
   - Max 1 decimal place validation
   - DriverTextFieldStyle with large title font
4. **Price Comparison Card** (shows when `newPrice != nil`):
   - Original price | arrow | New price
   - Color coding: green for decrease, red for increase
5. **Submit Button:**
   - "Submit Adjustment" text
   - Disabled when `!isValid` or `isSubmitting`
   - Shows ProgressView when submitting
   - DriverPrimaryButtonStyle
6. **Error Message:** Displays `errorMessage` if set

**Overlay States:**

**Waiting for Approval Overlay** (`isWaitingForApproval == true`):
```swift
ZStack {
    Color.black.opacity(0.6).ignoresSafeArea()
    VStack {
        ProgressView().tint(.white).scaleEffect(1.5)
        Text("Waiting for customer approval...")
    }
    .padding(xxl)
    .background(Color.driverPrimary)
    .clipShape(RoundedRectangle(cornerRadius: lg))
}
```

**Success Overlay** (`wasApproved == true`):
```swift
ZStack {
    Color.black.opacity(0.6).ignoresSafeArea()
    VStack {
        Image(systemName: "checkmark.circle.fill")
            .font(.system(size: 64))
            .foregroundStyle(Color.driverSuccess)
        Text(autoApproved ? "Auto-Approved" : "Customer Approved")
        if autoApproved { Text("Price Decreased") }
    }
    .padding(xxl)
    .background(Color.driverSuccess.opacity(0.9))
    .clipShape(RoundedRectangle(cornerRadius: lg))
}
```

**Decline Overlay** (`wasApproved == false`):
```swift
ZStack {
    Color.black.opacity(0.6).ignoresSafeArea()
    VStack {
        Image(systemName: "xmark.circle.fill")
            .font(.system(size: 64))
            .foregroundStyle(Color.driverError)
        Text("Customer Declined")
        if let tripFee { Text("Trip fee: $\(tripFee)") }
    }
    .padding(xxl)
    .background(Color.driverError.opacity(0.9))
    .clipShape(RoundedRectangle(cornerRadius: lg))
}
```

### ActiveJobView Integration

**File:** `JunkOS-Driver/Views/ActiveJob/ActiveJobView.swift`

Added "Adjust Volume" NavigationLink in `.arrived` status case:

```swift
case .arrived:
    VStack(spacing: DriverSpacing.md) {
        BeforePhotosView(viewModel: viewModel)

        NavigationLink(destination: VolumeAdjustmentView(
            jobId: job.id,
            originalEstimate: job.volumeEstimate
        )) {
            Label("Adjust Volume", systemImage: "arrow.up.arrow.down.circle")
                .font(DriverTypography.body)
                .foregroundStyle(Color.driverPrimary)
                .frame(maxWidth: .infinity)
                .padding(DriverSpacing.md)
                .background(Color.driverPrimary.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(.horizontal, DriverSpacing.xl)
    }
```

Button appears below BeforePhotosView, does not block primary workflow (before photos remain required to continue).

### DriverAPIClient Extension

**File:** `JunkOS-Driver/Services/DriverAPIClient.swift`

```swift
// MARK: - Volume Adjustment

func proposeVolumeAdjustment(jobId: String, actualVolume: Double) async throws -> VolumeProposalResponse {
    struct Body: Encodable {
        let actual_volume: Double
    }
    return try await request(
        "/api/drivers/jobs/\(jobId)/volume",
        method: "POST",
        body: Body(actual_volume: actualVolume)
    )
}
```

### VolumeProposalResponse Model

**File:** `JunkOS-Driver/Models/JobModels.swift`

```swift
// MARK: - Volume Adjustment

struct VolumeProposalResponse: Codable {
    let success: Bool
    let newPrice: Double?
    let originalPrice: Double?
    let autoApproved: Bool?

    enum CodingKeys: String, CodingKey {
        case success
        case newPrice = "new_price"
        case originalPrice = "original_price"
        case autoApproved = "auto_approved"
    }
}
```

### SocketIOManager Extension

**File:** `JunkOS-Driver/Services/SocketIOManager.swift`

Added Socket.IO listeners inside `connect()` method:

```swift
// Listen for volume adjustment approval
socket?.on("volume:approved") { data, _ in
    NotificationCenter.default.post(
        name: NSNotification.Name("socket:volume:approved"),
        object: nil,
        userInfo: data.first as? [String: Any]
    )
}

// Listen for volume adjustment decline
socket?.on("volume:declined") { data, _ in
    NotificationCenter.default.post(
        name: NSNotification.Name("socket:volume:declined"),
        object: nil,
        userInfo: data.first as? [String: Any]
    )
}
```

Follows Phase 4 NotificationCenter bridge pattern for `job:new` and `job:accepted` events.

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **Decimal keyboard with input filtering:** Only digits and single decimal point allowed, max 1 decimal place (onChange validation prevents invalid input)
2. **NotificationCenter bridge pattern:** Reused Phase 4 pattern for Socket.IO event forwarding to SwiftUI views (cleaner than @Observable property watching)
3. **Auto-approve immediate success:** No waiting spinner for price decreases - shows success overlay immediately when `response.autoApproved == true`
4. **Decline shows trip fee:** Extract `trip_fee` from Socket.IO payload userInfo and display in decline overlay
5. **Price comparison color coding:** Green for price decrease (customer-friendly), red for price increase (requires approval)
6. **Non-blocking placement:** "Adjust Volume" button appears below BeforePhotosView (optional action, does not block before photo upload requirement)
7. **Overlay-based status UI:** Full-screen overlays for waiting/approved/declined states (clear visual feedback, blocks interaction during waiting)

## Testing Notes

### Manual Testing Checklist
- [ ] Navigate to VolumeAdjustmentView from ActiveJobView when job status = arrived
- [ ] Volume input field shows decimal keyboard
- [ ] Input validation prevents multiple decimal points and more than 1 decimal place
- [ ] Submit button disabled when input empty or invalid
- [ ] API call sends POST /api/drivers/jobs/:id/volume with actual_volume
- [ ] Price comparison card shows original → new price after API response
- [ ] Auto-approve (price decrease) shows immediate success overlay with "Auto-Approved - Price Decreased"
- [ ] Price increase shows waiting overlay with spinner and "Waiting for customer approval..."
- [ ] Socket.IO volume:approved event triggers success overlay
- [ ] Socket.IO volume:declined event triggers decline overlay with trip fee
- [ ] Haptic feedback on success (success()) and error (error())
- [ ] Navigation back to ActiveJobView after approval/decline

### Integration Testing
- [ ] End-to-end volume adjustment flow: driver proposes → customer receives push → customer approves → driver sees approval
- [ ] End-to-end decline flow: driver proposes → customer declines → driver sees decline with trip fee
- [ ] Auto-approve flow: driver proposes lower volume → no push sent → driver sees immediate success

## Integration Points

### Dependencies
- **Phase 5-01**: Backend volume adjustment endpoints (POST /api/drivers/jobs/:id/volume)
- **Phase 5-01**: Socket.IO events (volume:approved, volume:declined)
- **Phase 4**: NotificationCenter bridge pattern for Socket.IO events
- **Phase 4**: DriverAPIClient async/await request pattern
- **Phase 2**: DriverDesignSystem (colors, typography, spacing)
- **Phase 2**: HapticManager for success/error feedback

### Enables
- **Phase 5 Plan 3**: Customer iOS actionable notification handler (UNNotificationCategory for approve/decline buttons)
- **Phase 5 Plan 4**: End-to-end volume adjustment verification across driver app, backend, and customer app

## Implementation Notes

### Input Filtering Pattern
```swift
.onChange(of: viewModel.volumeInput) { oldValue, newValue in
    // Filter input: only allow digits and single decimal point
    let filtered = newValue.filter { $0.isNumber || $0 == "." }
    let decimalCount = filtered.filter { $0 == "." }.count
    if decimalCount > 1 {
        viewModel.volumeInput = oldValue
    } else if filtered != newValue {
        viewModel.volumeInput = filtered
    } else {
        // Limit to 1 decimal place
        if let decimalIndex = filtered.firstIndex(of: ".") {
            let afterDecimal = filtered[filtered.index(after: decimalIndex)...]
            if afterDecimal.count > 1 {
                viewModel.volumeInput = oldValue
            }
        }
    }
}
```

Prevents:
- Non-numeric characters
- Multiple decimal points
- More than 1 decimal place

### NotificationCenter Bridge Pattern (from Phase 4)
```swift
// SocketIOManager.swift
socket?.on("volume:approved") { data, _ in
    NotificationCenter.default.post(
        name: NSNotification.Name("socket:volume:approved"),
        object: nil,
        userInfo: data.first as? [String: Any]
    )
}

// VolumeAdjustmentViewModel.swift
NotificationCenter.default.publisher(for: NSNotification.Name("socket:volume:approved"))
    .receive(on: RunLoop.main)
    .sink { [weak self] _ in
        self?.wasApproved = true
        self?.isWaitingForApproval = false
        HapticManager.shared.success()
    }
    .store(in: &cancellables)
```

Clean separation of concerns: SocketIOManager handles Socket.IO, ViewModel handles SwiftUI state updates via Combine publishers.

## Task Breakdown

### Task 1: Add API method and response models for volume adjustment
**Duration:** ~1.5 minutes
**Commit:** 5b3b529

**Changes:**
- Added `VolumeProposalResponse` model to JobModels.swift with success, newPrice, originalPrice, autoApproved fields
- Added `proposeVolumeAdjustment(jobId:actualVolume:)` async method to DriverAPIClient
- Added Socket.IO listeners for `volume:approved` and `volume:declined` events in SocketIOManager
- Added NotificationCenter bridge for volume events (consistent with Phase 4 job feed pattern)

**Verification:** Grep confirmed proposeVolumeAdjustment method, VolumeProposalResponse struct, and volume:approved listener exist.

### Task 2: Create VolumeAdjustmentView and ViewModel with ActiveJobView integration
**Duration:** ~1.25 minutes
**Commit:** 0480a38

**Changes:**
- Created VolumeAdjustmentViewModel.swift with @Observable pattern, Combine publishers, and proposeAdjustment async method
- Created VolumeAdjustmentView.swift with decimal input, price comparison card, and status overlays
- Updated ActiveJobView.swift to add "Adjust Volume" NavigationLink in .arrived case
- Added input filtering logic for decimal keyboard (max 1 decimal place)
- Added waiting, approved, and declined overlay states

**Verification:** Grep confirmed VolumeAdjustmentViewModel class, VolumeAdjustmentView struct, and NavigationLink in ActiveJobView exist.

## Performance

**Execution time:** 2.75 minutes (165 seconds)
**Tasks completed:** 2/2
**Commits:** 2
**Files created:** 2
**Files modified:** 4

## Next Steps

1. **Phase 5 Plan 3**: iOS customer app actionable notification handlers (UNNotificationCategory for approve/decline buttons)
2. **Phase 5 Plan 4**: End-to-end volume adjustment verification with real devices
3. **Phase 6**: Auto transport pricing and dual-service support (if applicable)

## Self-Check: PASSED

### Files Created
- [✓] JunkOS-Driver/ViewModels/VolumeAdjustmentViewModel.swift exists and contains VolumeAdjustmentViewModel class
- [✓] JunkOS-Driver/Views/ActiveJob/VolumeAdjustmentView.swift exists and contains VolumeAdjustmentView struct

### Files Modified
- [✓] JunkOS-Driver/Services/DriverAPIClient.swift exists and contains proposeVolumeAdjustment method
- [✓] JunkOS-Driver/Services/SocketIOManager.swift exists and contains volume:approved and volume:declined listeners
- [✓] JunkOS-Driver/Models/JobModels.swift exists and contains VolumeProposalResponse struct
- [✓] JunkOS-Driver/Views/ActiveJob/ActiveJobView.swift exists and contains NavigationLink to VolumeAdjustmentView

### Commits Exist
- [✓] 5b3b529: feat(05-02): add volume adjustment API method and Socket.IO listeners
- [✓] 0480a38: feat(05-02): add volume adjustment UI and ActiveJobView integration

### Key Functions Exist
```bash
grep -n "func proposeVolumeAdjustment" JunkOS-Driver/Services/DriverAPIClient.swift
# 231:    func proposeVolumeAdjustment(jobId: String, actualVolume: Double) async throws -> VolumeProposalResponse {

grep -n "struct VolumeAdjustmentView" JunkOS-Driver/Views/ActiveJob/VolumeAdjustmentView.swift
# 10:struct VolumeAdjustmentView: View {

grep -n "final class VolumeAdjustmentViewModel" JunkOS-Driver/ViewModels/VolumeAdjustmentViewModel.swift
# 12:final class VolumeAdjustmentViewModel {
```

All verification checks passed.
