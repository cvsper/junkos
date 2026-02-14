---
phase: 02-pricing-booking
plan: 04
subsystem: booking-wizard
tags: [wizard, photos, schedule, pricing, api-integration]
dependency_graph:
  requires:
    - 02-02-wizard-foundation
    - 02-03-address-input
  provides:
    - photo-upload-wizard-step
    - schedule-wizard-step
    - pricing-api-integration
    - running-price-estimate
  affects:
    - booking-wizard-flow
    - pricing-display
tech_stack:
  added:
    - backend-pricing-api-integration
  patterns:
    - wizard-step-completion
    - async-pricing-refresh
    - expandable-price-breakdown
key_files:
  created: []
  modified:
    - JunkOS-Clean/JunkOS/Views/PhotoUploadView.swift
    - JunkOS-Clean/JunkOS/Views/DateTimePickerView.swift
    - JunkOS-Clean/JunkOS/Services/APIClient.swift
    - JunkOS-Clean/JunkOS/ViewModels/BookingWizardViewModel.swift
    - JunkOS-Clean/JunkOS/Views/BookingWizardView.swift
    - JunkOS-Clean/JunkOS/Views/ServiceSelectionView.swift
    - JunkOS-Clean/JunkOS/Models/BookingModels.swift
decisions:
  - title: "Photos are optional but encouraged"
    rationale: "User decision in plan - photos help pricing but shouldn't block flow"
    alternatives: ["Require at least 1 photo", "Make photos completely hidden"]
    impact: "Better UX for users who want to skip ahead"
  - title: "Pricing refresh triggers on step change"
    rationale: "Updates price estimate as customer progresses through wizard with more data"
    alternatives: ["Manual refresh button", "Refresh on each field change"]
    impact: "Automatic pricing updates provide real-time feedback without overwhelming API"
  - title: "Pricing API calls are best-effort (silent failure)"
    rationale: "Don't block user flow if pricing API is unavailable"
    alternatives: ["Show error to user", "Block navigation on API failure"]
    impact: "More resilient UX, user can continue even if pricing temporarily unavailable"
  - title: "Volume tier maps to item quantity approximation"
    rationale: "Backend expects items array, but wizard uses volume tiers - map tier to quantity estimate"
    alternatives: ["Add item selector before pricing", "Send volume tier as-is"]
    impact: "Simpler UX while still providing backend with usable data for pricing"
metrics:
  duration_minutes: 14
  tasks_completed: 2
  files_modified: 7
  lines_added: 367
  lines_removed: 111
  commits: 2
  completed_at: "2026-02-14T03:36:23Z"
---

# Phase 2 Plan 4: Photos, Schedule & Pricing API Integration

**One-liner:** Photo upload (optional) + schedule selection wired as wizard steps 2-3 with backend pricing API integration and expandable running price estimate

## What Was Built

### Task 1: Wizard Pattern Adaptation
**PhotoUploadView refactor:**
- Removed `NavigationLink` Continue button, replaced with `Button` calling `wizardVM.completeCurrentStep()`
- Added `@EnvironmentObject var wizardVM: BookingWizardViewModel`
- Removed `ScreenHeader` progress bar (wizard handles progress dots)
- Added encouragement message when no photos: "Photos help us provide accurate pricing. You can skip this step, but we recommend at least 1 photo."
- Photos optional (max 10), Continue button always enabled
- Kept existing photo grid, camera picker, gallery picker, tip box

**DateTimePickerView refactor:**
- Removed `NavigationLink` Continue button, replaced with `Button` calling `wizardVM.completeCurrentStep()`
- Added `@EnvironmentObject var wizardVM: BookingWizardViewModel`
- Removed `ScreenHeader` progress bar and `BookingSummaryPreview` (wizard has running price bar)
- Continue button enabled only when date AND time selected
- Kept date selector (horizontal scroll cards) and time slot section (vertical list)

**Commits:** 6b4e341

### Task 2: Pricing API Integration & Wizard Wiring
**APIClient.getPricingEstimate method:**
- POST to `/api/pricing/estimate` endpoint
- Parameters: `serviceType`, `volumeTier`, `vehicleInfo`, pickup/dropoff coordinates, `scheduledDate`
- For Junk Removal: maps `volumeTier` to items array with quantity approximation (1/4→2, 1/2→5, 3/4→10, Full→16)
- For Auto Transport: includes vehicle make/model/year, is_running, needs_enclosed_trailer
- Decodes snake_case response to `PricingEstimate` struct
- Returns: subtotal, service fee, volume discount, time surge, zone surge, total, estimated duration, recommended truck

**BookingWizardViewModel.refreshPricing:**
- Async method called when step changes
- Only calls API if `serviceType` is set (guard against incomplete data)
- Builds API request from `bookingData` properties
- Updates `bookingData.estimatedPrice` and `bookingData.priceBreakdown`
- Silent failure (logs error but doesn't show to user) - pricing is best-effort

**BookingWizardView updates:**
- Wired `PhotoUploadView()` as step 2 (case 2)
- Wired `DateTimePickerView()` as step 3 (case 3)
- Added `.onChange(of: wizardVM.currentStep)` handler to trigger `refreshPricing`
- Made price estimate bar expandable:
  - Collapsed: Shows "Estimated Total" with price and "Details" button
  - Expanded: Shows line items (subtotal, service fee, discounts, surcharges, total, estimated duration)
  - Tap "Details" to toggle with animation
  - `@State var isPriceExpanded = false`

**Commits:** 51ddada

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed legacy ServiceSelectionView compilation errors**
- **Found during:** Task 1 build verification
- **Issue:** Legacy `ServiceSelectionView.swift` referenced `viewModel.selectedServices`, `viewModel.hasSelectedServices`, `viewModel.serviceDetails` which don't exist in `ServiceSelectionViewModel`. Also referenced non-existent types: `CleanoutType`, `RoomOption`, `ItemOption`, `WeightCategory`
- **Fix:**
  - Changed view to use `bookingData.selectedServices` directly instead of `viewModel`
  - Added `@State var serviceDetails: String` for TextEditor binding
  - Created stub legacy types in `BookingModels.swift`: `CleanoutType` (enum), `RoomOption` (struct), `ItemOption` (struct), `WeightCategory` (enum)
  - Added missing `BookingData` properties: `cleanoutType`, `selectedRooms`, `selectedItems`, `estimatedWeight`
  - Added `description` property to `ServiceTier` enum
- **Files modified:** `ServiceSelectionView.swift`, `BookingModels.swift`
- **Commit:** 6b4e341 (same as Task 1)
- **Rationale:** This legacy view had compilation errors that blocked the entire project build. Since it's not used in the wizard flow (replaced by `ServiceTypeSelectionView`), I added minimal stub types to allow compilation without removing the file (which might break Xcode project references).

## Verification

All verification criteria from plan passed:

1. **PhotoUploadView adapted for wizard** ✓
   - No NavigationLink, calls `wizardVM.completeCurrentStep()`
   - No ScreenHeader progress bar
   - Compiles and works with BookingData via EnvironmentObject

2. **DateTimePickerView adapted for wizard** ✓
   - No NavigationLink, calls `wizardVM.completeCurrentStep()`
   - No ScreenHeader, no BookingSummaryPreview
   - Compiles and works with BookingData via EnvironmentObject

3. **APIClient.getPricingEstimate exists** ✓
   - POSTs to `/api/pricing/estimate`
   - Returns `PricingEstimate` struct
   - Decodes snake_case response

4. **Steps 2 and 3 wired in BookingWizardView** ✓
   - PhotoUploadView is step 2
   - DateTimePickerView is step 3

5. **Running price bar appears and updates** ✓
   - Shows after service selection (when `estimatedPrice` is not nil)
   - Updates via `.onChange(of: wizardVM.currentStep)`
   - Expandable for line-item breakdown

6. **Project compiles** ✓
   - `xcodebuild build` succeeds

## Self-Check

Verifying created/modified files exist and commits are valid:

```bash
# Check modified files
[ -f "JunkOS-Clean/JunkOS/Views/PhotoUploadView.swift" ] && echo "FOUND: PhotoUploadView.swift" || echo "MISSING"
[ -f "JunkOS-Clean/JunkOS/Views/DateTimePickerView.swift" ] && echo "FOUND: DateTimePickerView.swift" || echo "MISSING"
[ -f "JunkOS-Clean/JunkOS/Services/APIClient.swift" ] && echo "FOUND: APIClient.swift" || echo "MISSING"
[ -f "JunkOS-Clean/JunkOS/ViewModels/BookingWizardViewModel.swift" ] && echo "FOUND: BookingWizardViewModel.swift" || echo "MISSING"
[ -f "JunkOS-Clean/JunkOS/Views/BookingWizardView.swift" ] && echo "FOUND: BookingWizardView.swift" || echo "MISSING"
[ -f "JunkOS-Clean/JunkOS/Models/BookingModels.swift" ] && echo "FOUND: BookingModels.swift" || echo "MISSING"

# Check commits exist
git log --oneline | grep -q "6b4e341" && echo "FOUND: commit 6b4e341" || echo "MISSING"
git log --oneline | grep -q "51ddada" && echo "FOUND: commit 51ddada" || echo "MISSING"
```

**Result:**
- FOUND: PhotoUploadView.swift
- FOUND: DateTimePickerView.swift
- FOUND: APIClient.swift
- FOUND: BookingWizardViewModel.swift
- FOUND: BookingWizardView.swift
- FOUND: BookingModels.swift
- FOUND: commit 6b4e341
- FOUND: commit 51ddada

## Self-Check: PASSED

All files and commits verified.

## Success Criteria Met

✓ Customer can upload photos (optional, max 10)
✓ Photos display in grid preview with delete capability
✓ Customer can select date and time slot for pickup
✓ Running price estimate updates after photos and scheduling steps
✓ Photo step plugs into BookingWizardView as step 2
✓ Schedule step plugs into BookingWizardView as step 3
✓ APIClient can call backend pricing estimate endpoint
✓ Price bar is expandable to show breakdown
✓ Pricing API integration enables real estimates from backend

## Next Steps

**Phase 2, Plan 5:** Review & Confirm step - final booking review, summary display, submit booking to backend.
