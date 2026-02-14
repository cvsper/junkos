---
phase: 05-volume-adjustment
plan: 03
subsystem: customer-ios
tags: [volume-adjustment, notifications, push-actions, ui, apiClient]
dependency_graph:
  requires:
    - Phase 5 Plan 1 volume adjustment backend endpoints
    - Phase 4 push notification infrastructure (NotificationManager)
    - Phase 2 BookingResponse model and OrdersView
  provides:
    - VOLUME_ADJUSTMENT notification category with actionable buttons
    - In-app volume adjustment approval/decline UI
    - APIClient volume adjustment methods
    - Real-time booking list refresh on volume adjustment notifications
  affects:
    - NotificationManager (new category + action handlers)
    - APIClient (approve/decline methods)
    - APIModels BookingResponse (volume adjustment fields)
    - OrdersView (volume adjustment banner)
tech_stack:
  added:
    - UNNotificationAction for approve/decline buttons
    - NotificationCenter bridge for foreground refresh
  patterns:
    - Actionable push notifications with UNNotificationCategory
    - Notification action handling with immediate API calls
    - NotificationCenter publisher for cross-view event handling
    - Task-based async API calls from button actions
    - MainActor refresh callbacks for UI updates
key_files:
  created: []
  modified:
    - JunkOS-Clean/JunkOS/Managers/NotificationManager.swift
    - JunkOS-Clean/JunkOS/Services/APIClient.swift
    - JunkOS-Clean/JunkOS/Models/APIModels.swift
    - JunkOS-Clean/JunkOS/Views/OrdersView.swift
decisions:
  - Approve/Decline actions use .foreground option (opens app on tap for context)
  - Decline action marked .destructive (red button) to signal irreversible cancellation
  - Volume adjustment banner shows inline with booking card (contextually relevant)
  - Buttons call API then refresh list (optimistic-like UI update)
  - NotificationCenter event for foreground volume_adjustment pushes (auto-refresh without tap)
  - Added onRefresh callback to BookingCard for clean separation of concerns
metrics:
  duration_minutes: 3.01
  tasks_completed: 2
  commits: 2
  files_modified: 4
  completed_date: 2026-02-14
---

# Phase 5 Plan 3: Customer Volume Adjustment Notifications Summary

Customer iOS app volume adjustment notification handling complete: actionable push notification with lock-screen approve/decline buttons, in-app fallback UI banner, and API integration.

## One-liner

Actionable volume adjustment push notifications with approve/decline buttons on iOS lock screen, in-app fallback banner with same actions, and NotificationCenter-based foreground refresh.

## What Was Built

### NotificationManager Enhancements

**New Notification Category:**
- Added `volumeAdjustment = "VOLUME_ADJUSTMENT"` case to NotificationCategory enum
- Category title: "Volume Adjustment"

**Actionable Notification Registration:**
```swift
let approveAction = UNNotificationAction(
    identifier: "APPROVE_VOLUME",
    title: "Approve New Price",
    options: [.foreground]
)
let declineAction = UNNotificationAction(
    identifier: "DECLINE_VOLUME",
    title: "Decline & Cancel",
    options: [.destructive, .foreground]
)
```
- Approve: Green button, opens app with approval context
- Decline: Red button (destructive style), opens app with cancellation context
- Category options: `.customDismissAction` for explicit dismissal tracking

**Action Handling:**
- Intercepts APPROVE_VOLUME and DECLINE_VOLUME action identifiers before category routing
- Extracts `job_id` from notification `userInfo`
- Calls `APIClient.shared.approveVolumeAdjustment(jobId:)` or `declineVolumeAdjustment(jobId:)`
- Actions execute in Task context (async/await)
- Errors silently logged with `try?` (non-blocking for user)

**Foreground Refresh:**
- Posts `volumeAdjustmentReceived` NotificationCenter event when volume_adjustment notification arrives
- Enables OrdersView to auto-refresh booking list without user tap

**Type Fallback:**
- Added "volume_adjustment" to type-based category mapping (backend compatibility)

### APIClient Volume Adjustment Methods

**POST /api/jobs/{jobId}/volume/approve:**
```swift
func approveVolumeAdjustment(jobId: String) async throws -> [String: Any]
```
- Endpoint: `/api/jobs/{jobId}/volume/approve`
- Method: POST
- Returns: JSON dictionary with success/status
- Throws: APIClientError.serverError if non-200 response

**POST /api/jobs/{jobId}/volume/decline:**
```swift
func declineVolumeAdjustment(jobId: String) async throws -> [String: Any]
```
- Endpoint: `/api/jobs/{jobId}/volume/decline`
- Method: POST
- Returns: JSON dictionary with success/trip_fee
- Throws: APIClientError.serverError if non-200 response

Both methods:
- Auto-inject JWT auth header from Keychain
- Use createRequest helper for consistent configuration
- Return raw JSON dictionary (flexible response parsing)

### BookingResponse Model Extensions

Added three optional fields:
```swift
let volumeAdjustmentProposed: Bool?
let adjustedPrice: Double?
let adjustedVolume: Double?
```

**CodingKeys:**
- `volume_adjustment_proposed` → volumeAdjustmentProposed
- `adjusted_price` → adjustedPrice
- `adjusted_volume` → adjustedVolume

**Decoding:**
- Uses `try?` for optional field decoding (backward compatible)
- Fields default to nil if absent in response

**Encoding:**
- Uses `encodeIfPresent` for optional fields

### OrdersView In-App Banner

**Conditional Banner:**
- Displayed when `booking.volumeAdjustmentProposed == true`
- Positioned below booking card details, before card padding

**Banner Content:**
1. **Header:** Orange warning icon + "Price Adjustment Required" (semibold)
2. **Price Display:** "New price: $X.XX" (secondary text color)
3. **Action Buttons:**
   - **Approve:** Green background, white text, calls approve API
   - **Decline:** Red background, white text, calls decline API

**Button Behavior:**
```swift
Button {
    Task {
        try? await APIClient.shared.approveVolumeAdjustment(jobId: booking.bookingId)
        await MainActor.run {
            onRefresh()
        }
    }
}
```
- Execute API call in Task context
- Switch to MainActor for UI refresh callback
- Silent error handling with `try?`
- Refresh booking list after action (banner disappears when adjustment cleared)

**Banner Styling:**
- Orange background at 10% opacity (warning color)
- 12pt padding
- 12pt corner radius
- 8pt vertical spacing between elements
- 12pt horizontal spacing between buttons

**Real-Time Refresh:**
- Added `.onReceive` listener for `volumeAdjustmentReceived` NotificationCenter event
- Auto-refreshes booking list when volume adjustment push arrives while app is in foreground
- Also refreshes on `UIApplication.willEnterForegroundNotification` (existing behavior)

**BookingCard Refactoring:**
- Added `onRefresh: () -> Void` parameter to BookingCard
- Parent OrdersView passes `loadBookings` as callback
- Enables post-action refresh without tight coupling

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **Foreground action option**: Both approve/decline actions use `.foreground` to open app (provides context for action result)
2. **Destructive style for decline**: Decline action marked `.destructive` for red button styling (signals irreversible cancellation with trip fee)
3. **NotificationCenter bridge**: Use NotificationCenter publisher for foreground refresh (cleaner than @Observable property watching)
4. **Inline banner placement**: Volume adjustment banner embedded in BookingCard (contextually relevant, not global modal)
5. **Silent error handling**: Use `try?` for API calls from actions (don't interrupt user flow with error alerts)
6. **Callback pattern for refresh**: Pass `onRefresh` closure to BookingCard (separation of concerns, no direct parent access)
7. **Raw JSON return type**: Volume adjustment API methods return `[String: Any]` (flexible response handling, no strict model needed)

## Testing Notes

### Verification Checklist

**NotificationManager:**
- [x] VOLUME_ADJUSTMENT category registered
- [x] APPROVE_VOLUME action exists with "Approve New Price" title
- [x] DECLINE_VOLUME action exists with "Decline & Cancel" title
- [x] Action handling intercepts identifiers before category routing
- [x] job_id extracted from userInfo
- [x] APIClient approve/decline methods called in Task context
- [x] volumeAdjustmentReceived NotificationCenter event posted

**APIClient:**
- [x] approveVolumeAdjustment method exists
- [x] declineVolumeAdjustment method exists
- [x] Both methods use correct endpoints
- [x] Both methods auto-inject auth header

**BookingResponse:**
- [x] volumeAdjustmentProposed field exists
- [x] adjustedPrice field exists
- [x] adjustedVolume field exists
- [x] CodingKeys map to snake_case backend fields
- [x] Decoding handles missing fields (backward compatible)

**OrdersView:**
- [x] Volume adjustment banner conditional on volumeAdjustmentProposed == true
- [x] Banner displays adjusted price
- [x] Approve button calls approve API and refreshes list
- [x] Decline button calls decline API and refreshes list
- [x] NotificationCenter listener for volumeAdjustmentReceived
- [x] BookingCard accepts onRefresh callback

### Manual Testing (Next Session)

- [ ] Send test volume adjustment push from backend
- [ ] Verify notification shows on lock screen with approve/decline buttons
- [ ] Tap "Approve New Price" → app opens, API call succeeds, booking list updates
- [ ] Tap "Decline & Cancel" → app opens, API call succeeds, booking cancelled with trip fee
- [ ] Send push while app is in foreground → booking list auto-refreshes
- [ ] Open app to OrdersView → booking with volumeAdjustmentProposed shows orange banner
- [ ] Tap in-app "Approve" → banner disappears after refresh
- [ ] Tap in-app "Decline" → booking status changes to cancelled after refresh

## Integration Points

### Dependencies
- **Phase 5 Plan 1**: Backend volume adjustment endpoints (approve/decline/propose)
- **Phase 4**: Push notification infrastructure (NotificationManager, APNs registration)
- **Phase 2**: BookingResponse model and OrdersView structure

### Enables
- **Phase 5 Plan 4**: End-to-end volume adjustment verification (customer + driver + backend)

## Implementation Notes

### Notification Payload Structure

Backend must send:
```json
{
  "aps": {
    "alert": {
      "title": "Price Adjustment Required",
      "body": "Volume increased. New price: $150.00 (was $100.00)"
    },
    "category": "VOLUME_ADJUSTMENT",
    "sound": "default"
  },
  "job_id": "abc123",
  "new_price": "150.00",
  "original_price": "100.00",
  "type": "volume_adjustment"
}
```

Key fields:
- `aps.category`: Must match "VOLUME_ADJUSTMENT" for action buttons to appear
- `job_id`: Required for approve/decline API calls (String format)
- `type`: Fallback for category mapping if categoryIdentifier unavailable

### UI Flow Diagrams

**Lock Screen Flow:**
```
Push arrives → Lock screen notification shows
  ↓
Tap "Approve New Price"
  ↓
App opens → NotificationManager.userNotificationCenter(didReceive:)
  ↓
Extract job_id → APIClient.approveVolumeAdjustment(jobId:)
  ↓
Backend updates job → Returns success
  ↓
User opens OrdersView → Booking list refreshes → Banner disappears
```

**In-App Flow:**
```
Push arrives while app open → NotificationCenter posts volumeAdjustmentReceived
  ↓
OrdersView receives event → loadBookings() refreshes list
  ↓
Booking card renders with volumeAdjustmentProposed == true
  ↓
Orange banner appears with adjusted price and buttons
  ↓
User taps "Approve" → APIClient.approveVolumeAdjustment()
  ↓
onRefresh() callback → loadBookings() → Banner disappears
```

### Code Organization

**NotificationManager:**
- Line 20: volumeAdjustment case added to enum
- Line 100-133: registerNotificationCategories() with action registration
- Line 203-250: didReceive response handler with action interception
- Line 257-262: handleNotificationAction with NotificationCenter post

**APIClient:**
- Line 469-494: Volume Adjustment section with approve/decline methods

**APIModels:**
- Line 141-143: Volume adjustment fields
- Line 166-168: CodingKeys
- Line 215-217: Decoding
- Line 233-235: Encoding

**OrdersView:**
- Line 71-73: volumeAdjustmentReceived listener
- Line 102-104: Pass onRefresh callback to BookingCard
- Line 137-138: BookingCard signature with onRefresh parameter
- Line 197-255: Volume adjustment banner conditional

## Task Breakdown

### Task 1: Add VOLUME_ADJUSTMENT notification category with approve/decline actions
**Duration:** ~1.5 minutes
**Commit:** 3ed67e9

**Changes:**
- Added volumeAdjustment case to NotificationCategory enum (line 20)
- Updated registerNotificationCategories() with action registration (lines 100-133)
- Added action handling in didReceive response (lines 234-246)
- Added "volume_adjustment" to type fallback switch (line 260)
- Posted volumeAdjustmentReceived NotificationCenter event (line 259)
- Added approveVolumeAdjustment API method (lines 469-479)
- Added declineVolumeAdjustment API method (lines 481-491)
- Added volumeAdjustmentProposed, adjustedPrice, adjustedVolume to BookingResponse (lines 141-143)
- Added CodingKeys for new fields (lines 166-168)
- Added decoding for new fields (lines 215-217)
- Added encoding for new fields (lines 233-235)

**Files modified:**
- NotificationManager.swift (3 sections)
- APIClient.swift (1 section)
- APIModels.swift (4 sections)

**Verification:** Grep confirmed all key identifiers present.

### Task 2: Add in-app volume adjustment pending banner to OrdersView
**Duration:** ~1.5 minutes
**Commit:** 59561d6

**Changes:**
- Added volumeAdjustmentReceived NotificationCenter listener (line 71-73)
- Passed onRefresh callback to BookingCard (line 104)
- Updated BookingCard signature with onRefresh parameter (line 138)
- Added volume adjustment banner conditional (lines 197-255)
  - Orange warning icon + header
  - Adjusted price display
  - Approve button (green) with API call
  - Decline button (red) with API call
  - MainActor refresh callback after action
- Added Preview for BookingCard with mock data (lines 348-367)

**Files modified:**
- OrdersView.swift (4 sections)

**Verification:** Grep confirmed banner elements, conditional, and button actions.

## Performance

**Execution time:** 3.01 minutes (181 seconds)
**Tasks completed:** 2/2
**Commits:** 2
**Files modified:** 4

## Next Steps

1. **Phase 5 Plan 4**: End-to-end verification with real backend volume adjustment flow
2. Manual testing with test push notifications
3. Verify lock screen action buttons appear correctly
4. Verify in-app banner shows and dismisses after actions

## Self-Check: PASSED

### Files Modified
- [✓] JunkOS-Clean/JunkOS/Managers/NotificationManager.swift exists and contains VOLUME_ADJUSTMENT, APPROVE_VOLUME, DECLINE_VOLUME
- [✓] JunkOS-Clean/JunkOS/Services/APIClient.swift exists and contains approveVolumeAdjustment, declineVolumeAdjustment
- [✓] JunkOS-Clean/JunkOS/Models/APIModels.swift exists and contains volumeAdjustmentProposed, adjustedPrice, adjustedVolume
- [✓] JunkOS-Clean/JunkOS/Views/OrdersView.swift exists and contains Price Adjustment Required banner, Approve/Decline buttons

### Commits Exist
- [✓] 3ed67e9: feat(05-03): add VOLUME_ADJUSTMENT notification category with approve/decline actions
- [✓] 59561d6: feat(05-03): add in-app volume adjustment pending banner to OrdersView

### Key Artifacts Verified
```bash
# NotificationManager
grep -n "VOLUME_ADJUSTMENT" JunkOS-Clean/JunkOS/Managers/NotificationManager.swift
# 20:    case volumeAdjustment = "VOLUME_ADJUSTMENT"

grep -n "APPROVE_VOLUME" JunkOS-Clean/JunkOS/Managers/NotificationManager.swift
# 117:            identifier: "APPROVE_VOLUME",
# 234:        if actionIdentifier == "APPROVE_VOLUME" || actionIdentifier == "DECLINE_VOLUME" {
# 236:                if actionIdentifier == "APPROVE_VOLUME" {

# APIClient
grep -n "approveVolumeAdjustment" JunkOS-Clean/JunkOS/Services/APIClient.swift
# 469:    func approveVolumeAdjustment(jobId: String) async throws -> [String: Any] {

# APIModels
grep -n "volumeAdjustmentProposed" JunkOS-Clean/JunkOS/Models/APIModels.swift
# 141:    let volumeAdjustmentProposed: Bool?
# 166:        case volumeAdjustmentProposed = "volume_adjustment_proposed"
# 215:        volumeAdjustmentProposed = try? container.decode(Bool.self, forKey: .volumeAdjustmentProposed)
# 233:        try container.encodeIfPresent(volumeAdjustmentProposed, forKey: .volumeAdjustmentProposed)

# OrdersView
grep -n "Price Adjustment Required" JunkOS-Clean/JunkOS/Views/OrdersView.swift
# 202:                        Text("Price Adjustment Required")
```

All verification checks passed.
