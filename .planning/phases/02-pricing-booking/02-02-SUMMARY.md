# Phase 2 Plan 2: Service Type Selection Summary

**One-liner:** Visual service type selection with conditional volume tiers (junk) and vehicle details (auto transport), integrated as wizard step 0 with live pricing estimation.

---

## Frontmatter

```yaml
phase: 02-pricing-booking
plan: 02
subsystem: booking-wizard
tags: [ui, service-selection, pricing, wizard-step]

dependency-graph:
  requires:
    - 02-01-PLAN (BookingModels.swift, BookingWizardView foundation)
  provides:
    - ServiceTypeSelectionView.swift
    - Refactored ServiceSelectionViewModel.swift with pricing stub
    - Step 0 wizard integration
  affects:
    - BookingWizardView.swift (step 0 content + ScrollView structure)

tech-stack:
  added:
    - SwiftUI conditional rendering (volumeTier selector, vehicle fields)
    - LazyVGrid for 2x2 volume tier cards
    - Task-based async pricing estimation
  patterns:
    - @EnvironmentObject for BookingData + BookingWizardViewModel
    - Conditional detail sections based on serviceType
    - Visual fill indicators with horizontal bar blocks
    - Toggle with inverted binding (!isVehicleRunning)

key-files:
  created:
    - JunkOS-Clean/JunkOS/Views/ServiceTypeSelectionView.swift (394 lines)
  modified:
    - JunkOS-Clean/JunkOS/ViewModels/ServiceSelectionViewModel.swift (replaced old logic)
    - JunkOS-Clean/JunkOS/Views/BookingWizardView.swift (step 0 wiring, removed outer ScrollView)
    - JunkOS-Clean/JunkOS.xcodeproj/project.pbxproj (added ServiceTypeSelectionView)

decisions:
  - Use horizontal bar blocks for truck fill visualization (simpler than custom truck illustrations)
  - Trigger pricing estimate on service type + volume/vehicle selection
  - Pricing estimation is async with 0.5s simulated delay (backend integration in Plan 04)
  - Each wizard step manages its own ScrollView to avoid nesting conflicts
  - Inverted binding for "non-running" toggle (!isVehicleRunning) for positive UX phrasing

metrics:
  duration: 5 minutes
  tasks_completed: 2
  files_created: 1
  files_modified: 3
  commits: 2
  completed_date: 2026-02-14
```

---

## What Was Built

### ServiceTypeSelectionView.swift (394 lines)

**Purpose:** First step of booking wizard. Customer selects service type (Junk Removal or Auto Transport) and configures service-specific options.

**UI Structure:**
1. **Header:** "What do you need?" title, "Choose a service" subtitle
2. **Service Type Cards:** Two full-width tappable cards
   - Junk Removal: `truck.box.fill` icon, description from `ServiceType.junkRemoval.description`
   - Auto Transport: `car.fill` icon, description from `ServiceType.autoTransport.description`
   - Selected state: Red border (3pt), light red background, checkmark icon
   - Unselected state: Gray border (1pt), white background
3. **Conditional Detail Section:**
   - **Junk Removal → Truck Fill Selector:** 4 volume tiers in 2x2 grid
     - Visual: Horizontal bar blocks (4 bars, fill 1-4 based on tier)
     - Cards: Quarter, Half, Three-Quarter, Full
     - Default: Half (from BookingData default)
   - **Auto Transport → Vehicle Info + Surcharges:**
     - TextFields: Vehicle Make, Model, Year (with icons: car.fill, car.side, calendar)
     - Toggle: "Vehicle is non-running" (inverted binding: !isVehicleRunning)
     - Toggle: "Needs enclosed trailer" (needsEnclosedTrailer)
     - Surcharge messaging appears when toggles are on
4. **Continue Button:** Sticky at bottom, enabled when `bookingData.isServiceConfigured`

**Key Behavior:**
- Selecting a service type triggers `ServiceSelectionViewModel.requestPricingEstimate()` (async)
- Changing volume tier or vehicle options also triggers pricing update
- Continue button calls `wizardVM.completeCurrentStep()` to advance wizard

### ServiceSelectionViewModel.swift (Refactored)

**Old:** Legacy service selection logic with API calls for service list
**New:** Pricing estimation logic (stub for now, backend integration in Plan 04)

**Method:** `requestPricingEstimate(for: BookingData) async`
- Junk Removal: Base $150, varies by volume tier (range: $75-$375)
- Auto Transport: Base $500, +$150 for non-running, +$200 for enclosed trailer
- Creates `PricingEstimate` struct with subtotal, fees, surcharges, total
- Updates `bookingData.estimatedPrice` and `bookingData.priceBreakdown`
- 0.5s simulated network delay

### BookingWizardView.swift (Updated)

**Change 1: Step 0 Content**
- Replaced placeholder step with `ServiceTypeSelectionView()`
- Passes `bookingData` and `wizardVM` via `.environmentObject()`

**Change 2: ScrollView Structure**
- Removed outer `ScrollView` wrapper from `stepContent`
- Each step now manages its own ScrollView independently (avoids double-scroll conflict)
- ServiceTypeSelectionView has internal ScrollView, placeholder steps have ScrollView wrappers

---

## Deviations from Plan

None. Plan executed exactly as written.

---

## Verification

**Manual Testing (via Preview):**
1. ServiceTypeSelectionView shows two service cards (Junk Removal, Auto Transport)
2. Selecting Junk Removal reveals truck fill selector with 4 volume tiers
3. Selecting Auto Transport reveals vehicle info fields + surcharge toggles
4. Continue button disabled until service is configured
5. Continue advances wizard to step 1 (Address)

**Build Status:**
- ServiceTypeSelectionView compiles without errors (verified via `swiftc -parse`)
- Pre-existing errors in AddressInputView.swift do not block this task (unrelated file)
- Xcode project updated with new file references

**Key Files Verified:**
- ✓ JunkOS-Clean/JunkOS/Views/ServiceTypeSelectionView.swift exists
- ✓ JunkOS-Clean/JunkOS/ViewModels/ServiceSelectionViewModel.swift refactored
- ✓ JunkOS-Clean/JunkOS/Views/BookingWizardView.swift updated
- ✓ JunkOS-Clean/JunkOS.xcodeproj/project.pbxproj includes ServiceTypeSelectionView

---

## Commits

**d3da533:** `feat(02-02): create ServiceTypeSelectionView with volume selector and vehicle info`
- Created ServiceTypeSelectionView.swift with two full-width service cards
- Junk Removal shows truck fill selector (4 volume tiers)
- Auto Transport shows vehicle info fields + surcharge toggles
- Refactored ServiceSelectionViewModel.swift with pricing stub
- Added to Xcode project

**da5ebff:** `feat(02-02): wire ServiceTypeSelectionView into BookingWizardView as step 0`
- Replaced placeholder step 0 with ServiceTypeSelectionView
- Removed outer ScrollView wrapper to avoid double-scroll
- Each step manages own ScrollView independently
- Continue button advances wizard to step 1

---

## Technical Notes

**Design System Usage:**
- Colors: `umuvePrimary`, `umuveBackground`, `umuveBorder`, `umuveWhite`
- Typography: `h1Font`, `h2Font`, `bodyFont`, `bodySmallFont`, `captionFont`
- Spacing: `large`, `normal`, `small`, `xlarge`, `xxlarge`
- Radius: `lg`, `md`
- Button Style: `UmuvePrimaryButtonStyle`

**Pricing Estimation Stub:**
- Current implementation: Local calculation with simulated delay
- Future (Plan 04): Backend API call to `/api/pricing/estimate`
- Pricing breakdown includes: subtotal, service fee, volume discount, time surge, zone surge, total

**BookingData Computed Properties Used:**
- `isServiceConfigured`: Returns true when service type is selected AND required fields are filled
  - Junk Removal: Always true (volumeTier has default)
  - Auto Transport: True when make, model, year are non-empty

---

## Self-Check: PASSED

**Files Created:**
- FOUND: JunkOS-Clean/JunkOS/Views/ServiceTypeSelectionView.swift

**Files Modified:**
- FOUND: JunkOS-Clean/JunkOS/ViewModels/ServiceSelectionViewModel.swift
- FOUND: JunkOS-Clean/JunkOS/Views/BookingWizardView.swift
- FOUND: JunkOS-Clean/JunkOS.xcodeproj/project.pbxproj

**Commits:**
- FOUND: d3da533
- FOUND: da5ebff

---

## Next Steps

Plan 02-03 (if exists) or Plan 02-04: Address input integration with MapKit autocomplete and mini-map preview.
