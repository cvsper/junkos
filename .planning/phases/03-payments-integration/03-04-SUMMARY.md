---
phase: 03-payments-integration
plan: 04
subsystem: driver-app-earnings
tags: [earnings-dashboard, payout-status, api-integration]
dependency_graph:
  requires:
    - backend-earnings-api
    - driver-api-client
    - earnings-models
  provides:
    - earnings-dashboard-ui
    - payout-status-badges
    - earnings-period-filtering
  affects:
    - driver-earnings-tab
    - driver-navigation
tech_stack:
  added:
    - SwiftUI-task-modifier
    - SwiftUI-refreshable
    - ISO8601DateFormatter
  patterns:
    - api-driven-viewmodel
    - period-based-filtering
    - payout-status-tracking
    - error-recovery-ui
key_files:
  created: []
  modified:
    - JunkOS-Driver/Services/DriverAPIClient.swift: "Added getEarningsHistory() endpoint and EarningsHistoryResponse models"
    - JunkOS-Driver/Models/EarningsModels.swift: "Added PayoutStatus enum and allTimeEarnings to summary"
    - JunkOS-Driver/ViewModels/EarningsViewModel.swift: "Added fetchEarnings() with API integration, filteredEntries, and All Time period"
    - JunkOS-Driver/Views/Earnings/EarningsView.swift: "Added .task/.refreshable, loading states, error banner, payout status badges, 4-period picker"
decisions:
  - context: "Date range filters"
    choice: "4 segments: Today, This Week, This Month, All Time"
    rationale: "Covers all use cases without overwhelming UI — matches plan requirements and backend summary periods"
  - context: "Payout status colors"
    choice: "Pending=amber, Processing=blue, Paid=green"
    rationale: "Visual hierarchy: amber warns attention needed, blue shows in-progress, green confirms completion"
  - context: "Loading behavior"
    choice: "Show spinner only on initial load, not during refresh"
    rationale: "Refreshable provides its own UI feedback — avoid duplicate loading indicators"
  - context: "Error handling"
    choice: "Dismissible banner with retry button at top"
    rationale: "Non-blocking error display lets users continue viewing cached data and easily retry"
metrics:
  duration_minutes: 2.5
  tasks_completed: 2
  files_modified: 4
  commits: 2
  completed_at: "2026-02-14T11:45:32Z"
---

# Phase 03 Plan 04: Driver Earnings Dashboard API Integration Summary

**One-liner:** API-connected earnings dashboard with payout status badges (Pending/Processing/Paid), 4 date range filters (today/week/month/all-time), pull-to-refresh, and error recovery.

## What Was Built

### 1. API Client Integration (DriverAPIClient.swift)

**getEarningsHistory() method**
- Calls `/api/payments/earnings/history` endpoint
- Returns EarningsHistoryResponse with entries and summary
- Authenticated request using JWT from Keychain

**Response Models**
- `EarningsHistoryResponse`: Top-level response with success, entries array, summary
- `EarningsEntryResponse`: Per-job entry with id, job_id, address, amount, date, payout_status
- `EarningsSummaryResponse`: Period totals with today, week, month, all_time

**CodingKeys mapping**
- Snake case API fields → camelCase Swift properties
- `job_id` → `jobId`
- `payout_status` → `payoutStatus`
- `all_time` → `allTime`

### 2. Data Models Enhancement (EarningsModels.swift)

**PayoutStatus enum**
- Three states: `pending`, `processing`, `paid`
- `displayName` property: "Pending", "Processing", "Paid"
- `color` property: Returns string key for Color lookup
  - `pending` → "driverWarning" (amber)
  - `processing` → "driverPrimary" (blue)
  - `paid` → "driverSuccess" (green)

**EarningsSummary updates**
- Added `allTimeEarnings: Double` property
- Added `formattedAllTime: String` computed property
- Updated `empty` static to include `allTimeEarnings: 0`

**EarningsEntry updates**
- Changed `status: String` → `payoutStatus: PayoutStatus` (typed enum)
- Preserves existing `formattedAmount` and `formattedDate` computed properties

### 3. ViewModel API Integration (EarningsViewModel.swift)

**New EarningsPeriod case**
- Added `.all = "All Time"` to enum (now 4 cases)

**fetchEarnings() async method**
- Sets `isLoading = true` at start
- Calls `DriverAPIClient.shared.getEarningsHistory()`
- Maps API response to local models:
  - Summary: Maps today/week/month/allTime directly from API
  - Entries: Parses ISO 8601 date strings, maps payout status string to enum
- Uses `compactMap` for safe parsing with fallbacks
- Sets `errorMessage` on failure (keeps existing data)
- Sets `isLoading = false` after completion
- `@MainActor` to ensure UI updates on main thread

**filteredEntries computed property**
- Filters `entries` by `selectedPeriod` using Calendar date math
- `.today`: `calendar.isDateInToday($0.date)`
- `.week`: Filters dates >= 7 days ago
- `.month`: Filters dates >= 30 days ago
- `.all`: Returns all entries (no filter)

**displayedAmount update**
- Added `.all` case returning `summary.formattedAllTime`

**Error handling**
- Added `errorMessage: String?` property
- Cleared at start of fetch
- Set on catch with `error.localizedDescription`

### 4. Earnings Dashboard UI (EarningsView.swift)

**Data loading lifecycle**
- `.task { await viewModel.fetchEarnings() }` — Load on appear
- `.refreshable { await viewModel.fetchEarnings() }` — Pull-to-refresh support

**Error banner**
- Shows when `viewModel.errorMessage` is set
- Red background with white text
- "Retry" button triggers re-fetch
- Tap-to-dismiss (sets errorMessage to nil)
- Positioned above period picker

**Period picker updates**
- Now 4 segments: "Today", "This Week", "This Month", "All Time"
- Segmented picker style
- Updates `viewModel.selectedPeriod` binding

**Summary card enhancements**
- Shows `viewModel.displayedAmount` (switches based on period)
- Shows job count below amount: "\(filteredEntries.count) jobs"
- Caption style, tertiary color
- Only shown when entries exist

**Loading state**
- Condition: `viewModel.isLoading && viewModel.entries.isEmpty`
- Shows centered ProgressView with "Loading earnings..." text
- Does NOT show during refresh (refreshable has its own UI)

**Empty state**
- Condition: `viewModel.filteredEntries.isEmpty` (after loading completes)
- Shows EmptyStateView with dollar icon
- Message: "Complete jobs to start earning. Your earnings history will appear here."

**Entries list**
- Uses `viewModel.filteredEntries` instead of raw `entries`
- Period filtering handled automatically by viewModel

**EarningsRow updates**
- Layout change: `HStack(alignment: .top)` to accommodate badge
- Right side: VStack with amount and payout status badge
- Badge styling:
  - `entry.payoutStatus.displayName` text
  - `payoutStatusColor()` function maps enum to Color
  - Semi-transparent background: `color.opacity(0.1)`
  - Padding: 6px horizontal, 2px vertical
  - Rounded corners: 4px radius

**payoutStatusColor() function**
- Maps PayoutStatus enum to SwiftUI Color
- `pending` → `Color("driverWarning")`
- `processing` → `Color("driverPrimary")`
- `paid` → `Color("driverSuccess")`

## Implementation Details

### API Response Mapping Flow

```
Backend API Response
↓
EarningsHistoryResponse (DriverAPIClient)
↓
fetchEarnings() parsing (EarningsViewModel)
↓
EarningsSummary + [EarningsEntry] (local models)
↓
filteredEntries computed property
↓
EarningsView UI rendering
```

### Date Parsing Strategy

```swift
let iso8601Formatter = ISO8601DateFormatter()
if let dateString = entry.date, let parsedDate = iso8601Formatter.date(from: dateString) {
    date = parsedDate
} else {
    date = Date()  // Fallback to now if parsing fails
}
```

Uses ISO8601DateFormatter (not DateFormatter) for backend compatibility.

### Payout Status Parsing

```swift
let payoutStatus = PayoutStatus(rawValue: entry.payoutStatus) ?? .pending
```

Safe parsing with fallback to `.pending` if API returns unknown status.

### Period Filtering Logic

- **Today**: Uses `calendar.isDateInToday()` — handles time zone correctly
- **Week**: Filters `date >= (now - 7 days)`
- **Month**: Filters `date >= (now - 30 days)`
- **All Time**: Returns all entries without filtering

### Amount Display

**CRITICAL:** Amount field is `driver_payout_amount` from backend (already 80% take).

No client-side multiplication — displays API value directly:
```swift
amount: entry.amount,  // Already driver's 80% take from backend
```

This follows locked decision from 03-02: drivers see their take only, not full job price.

## Deviations from Plan

None — plan executed exactly as written.

## User Experience Flow

1. Driver opens Earnings tab
2. Loading spinner shows "Loading earnings..." (first load only)
3. Data fetches from backend API
4. Summary card shows total for default period (Today)
5. Job list appears with address, date, amount, payout status badge
6. Driver switches period picker → summary and list update instantly
7. Driver pulls down → refresh indicator shows → data reloads
8. If error occurs → red banner shows at top with "Retry" button
9. Driver taps banner or "Retry" → error dismisses / retries fetch

## Testing Notes

**Manual testing checklist:**
- [ ] Open Earnings tab → data loads automatically
- [ ] Switch between Today/Week/Month/All Time → amounts and job lists update
- [ ] Pull down on list → refresh indicator shows → data reloads
- [ ] Turn off network → error banner appears with retry button
- [ ] Tap banner → dismisses error
- [ ] Tap retry → re-attempts fetch
- [ ] Each job shows payout status badge with correct color
- [ ] Summary card shows job count
- [ ] Empty state shows when no earnings for selected period

**Expected API contract:**
- Endpoint: `GET /api/payments/earnings/history`
- Response: `{ success: bool, entries: [...], summary: { today, week, month, all_time } }`
- Entry fields: `id, job_id, address, amount (driver's 80%), date (ISO 8601), payout_status`

## Key Files Modified

**JunkOS-Driver/Services/DriverAPIClient.swift** (+45 lines)
- Added `getEarningsHistory()` method
- Added `EarningsHistoryResponse` with nested response models
- CodingKeys for snake_case → camelCase mapping

**JunkOS-Driver/Models/EarningsModels.swift** (+32 lines)
- Added `PayoutStatus` enum with displayName and color properties
- Added `allTimeEarnings` and `formattedAllTime` to EarningsSummary
- Changed `status: String` → `payoutStatus: PayoutStatus` in EarningsEntry

**JunkOS-Driver/ViewModels/EarningsViewModel.swift** (+77 lines)
- Added `.all` case to EarningsPeriod enum
- Added `errorMessage: String?` property
- Added `fetchEarnings() async` method with API integration
- Added `filteredEntries` computed property for period filtering
- Updated `displayedAmount` to handle `.all` case

**JunkOS-Driver/Views/Earnings/EarningsView.swift** (+70 lines)
- Added `.task` modifier for on-appear data loading
- Added `.refreshable` modifier for pull-to-refresh
- Added error banner with retry button
- Updated period picker to 4 segments (added All Time)
- Added loading state with ProgressView
- Updated to use `filteredEntries` instead of `entries`
- Added job count to summary card
- Updated EarningsRow with payout status badge
- Added `payoutStatusColor()` helper function

## Verification Results

✅ EarningsView loads data from backend on appear (`.task` modifier)
✅ Pull-to-refresh triggers API call (`.refreshable` modifier)
✅ Period filter has 4 options including "All Time" (enum updated)
✅ Each job row shows payout status badge with appropriate color (badge component added)
✅ Amounts are driver's 80% take from backend (no client-side calculation)
✅ Loading state shown during initial load (ProgressView when isLoading)
✅ Error states handled gracefully (dismissible banner with retry)
✅ Empty state shown when no earnings (EmptyStateView)

## Next Steps

**Phase 03 remaining plans:**
- 03-03: Driver app Stripe Connect onboarding (mandatory gate on first job accept)

**Future enhancements (out of scope for MVP):**
- Pagination for earnings history (backend unpaginated per research)
- Export earnings data (CSV/PDF)
- Per-job detail view (tap row to see full job details)
- Custom date range picker (beyond 4 segments)
- Weekly/monthly earnings graphs
- Tax reporting tools

## Self-Check

**Created files:** None (all modifications)

**Modified files:**
- ✅ JunkOS-Driver/Services/DriverAPIClient.swift exists and modified
- ✅ JunkOS-Driver/Models/EarningsModels.swift exists and modified
- ✅ JunkOS-Driver/ViewModels/EarningsViewModel.swift exists and modified
- ✅ JunkOS-Driver/Views/Earnings/EarningsView.swift exists and modified

**Commits:**
- ✅ 490a847 (Task 1: API integration with payout status)
- ✅ d118a46 (Task 2: UI with badges and loading states)

## Self-Check: PASSED

All files modified as expected. All commits present in git history.
