---
phase: 03-payments-integration
plan: 03
subsystem: driver-app-onboarding
tags: [stripe-connect, mandatory-gate, payout-settings, safari-view]
dependency_graph:
  requires:
    - stripe-connect-backend-endpoints
    - contractor-profile-model
    - driver-app-auth-flow
  provides:
    - mandatory-connect-onboarding-gate
    - connect-status-ui
    - payout-settings-connect
  affects:
    - driver-app-entry-flow
    - driver-profile-settings
tech_stack:
  added:
    - SFSafariViewController
    - StripeConnectViewModel
  patterns:
    - mandatory-onboarding-gate
    - fresh-account-link-generation
    - status-driven-ui
key_files:
  created:
    - JunkOS-Driver/ViewModels/StripeConnectViewModel.swift: "Connect status checking and onboarding flow"
    - JunkOS-Driver/Views/Auth/StripeConnectOnboardingView.swift: "Mandatory setup screen with SFSafariViewController"
  modified:
    - JunkOS-Driver/Services/DriverAPIClient.swift: "Added 3 Connect API methods + response models"
    - JunkOS-Driver/ViewModels/AppState.swift: "Added hasCompletedStripeConnect computed property"
    - JunkOS-Driver/JunkOSDriverApp.swift: "Added Connect gate before main tab view"
    - JunkOS-Driver/Views/Profile/PayoutSettingsView.swift: "Replaced manual bank form with Connect status UI"
decisions:
  - context: "Onboarding gate placement"
    choice: "After registration, before main app access"
    rationale: "Drivers cannot accept jobs without payout method — block early to prevent confusion"
  - context: "Account link caching"
    choice: "Generate fresh link on every tap, never cache"
    rationale: "Links expire in 5 minutes — caching would cause expired URL errors"
  - context: "Status checking"
    choice: "Check on view appear, after Safari dismissal"
    rationale: "Stripe onboarding is async — need to poll for completion"
metrics:
  duration_minutes: 2.3
  tasks_completed: 2
  files_modified: 6
  commits: 2
  completed_at: "2026-02-14T10:19:38Z"
---

# Phase 03 Plan 03: Driver Stripe Connect Onboarding Summary

**One-liner:** Mandatory Stripe Connect onboarding gate with SFSafariViewController + payout settings showing Connect status badges (not set up / pending / active).

## What Was Built

### 1. StripeConnectViewModel (New File)

**Location:** `JunkOS-Driver/ViewModels/StripeConnectViewModel.swift`

Observable state management for Stripe Connect onboarding:

**Properties:**
- `onboardingStatus: ConnectOnboardingStatus` — enum: loading, notSetUp, pendingVerification, active, failed
- `showSafari: Bool` — controls Safari sheet presentation
- `accountLinkURL: URL?` — onboarding URL from backend
- `isCreatingAccount: Bool` — loading state for button

**Methods:**
- `checkStatus()` — calls `/api/payments/connect/status`, maps response to enum
- `startOnboarding()` — creates account (idempotent) → gets fresh link → shows Safari
- `onSafariDismissed()` — re-checks status after user returns from browser

**Pattern:** Fresh account links generated every time, never cached (expire in 5 minutes).

### 2. StripeConnectOnboardingView (New File)

**Location:** `JunkOS-Driver/Views/Auth/StripeConnectOnboardingView.swift`

Full-screen mandatory setup gate that blocks app access until Connect is active.

**Layout:**
- Large creditcard icon (80pt, driverPrimary)
- "Set Up Payments" title
- "Connect your bank account..." subtitle
- Status indicator (loading / not set up / pending / active / failed)
- "Connect with Stripe" primary button
- Loading spinner during account creation

**Safari Integration:**
- `SafariView` UIViewControllerRepresentable wraps `SFSafariViewController`
- Sheet presentation: `.sheet(isPresented: $viewModel.showSafari)`
- On dismiss: checks status + reloads contractor profile

**Flow:**
1. Check status on appear
2. Tap "Connect with Stripe"
3. Create account → get link → open Safari
4. Complete onboarding in browser
5. Dismiss Safari → check status
6. If active → reload profile → progress to main app

### 3. API Client Connect Methods

**Location:** `JunkOS-Driver/Services/DriverAPIClient.swift`

Three new methods added:

```swift
func createConnectAccount() async throws -> ConnectAccountResponse
func createAccountLink() async throws -> ConnectAccountLinkResponse
func getConnectStatus() async throws -> ConnectStatusResponse
```

**Response models:**
- `ConnectAccountResponse` — success + account_id
- `ConnectAccountLinkResponse` — success + url + expires_at
- `ConnectStatusResponse` — success + status + charges_enabled + payouts_enabled + details_submitted

All use snake_case CodingKeys for backend compatibility.

### 4. App Entry Gate

**Location:** `JunkOS-Driver/JunkOSDriverApp.swift`

New condition added to app flow:

```swift
} else if !appState.isRegistered {
    ContractorRegistrationView(appState: appState)
} else if !appState.hasCompletedStripeConnect {
    StripeConnectOnboardingView(appState: appState)
} else {
    DriverTabView(appState: appState)
```

**Flow order:**
1. Splash
2. Onboarding (first launch)
3. Auth (if not logged in)
4. Role selection (if needed)
5. Registration (if not registered)
6. **Stripe Connect setup (NEW)**
7. Main tab view

No path to job feed without Connect setup complete.

### 5. AppState Enhancement

**Location:** `JunkOS-Driver/ViewModels/AppState.swift`

New computed property:

```swift
var hasCompletedStripeConnect: Bool {
    contractorProfile?.stripeConnectId != nil
}
```

Basic check — detailed status from API in onboarding view.

### 6. PayoutSettingsView Replacement

**Location:** `JunkOS-Driver/Views/Profile/PayoutSettingsView.swift`

**REMOVED:**
- Manual bank account form (accountHolderName, routingNumber, accountNumber, confirmAccountNumber, accountType)
- Simulated success flow
- Form validation logic

**ADDED:**
- Connect status card with badge icons (warning / clock / checkmark)
- Status-driven action buttons:
  - Not set up → "Set Up Stripe Connect"
  - Pending → "Complete Setup" + info text
  - Active → "Manage Payout Account" + "Connected" label
  - Failed → "Retry" button
- "How payouts work" info section:
  - "You earn 80% of each completed job"
  - "Payouts are sent after each job is marked complete"
  - "Funds typically arrive in 1-2 business days"
- Security note: "encrypted and securely handled by Stripe"

**Pattern:** Reuses StripeConnectViewModel for state, opens SFSafariViewController for all actions.

## Implementation Details

### Fresh Account Link Generation

Every tap of setup/complete/manage button:
1. Calls `createConnectAccount()` (idempotent)
2. Calls `createAccountLink()` (generates fresh URL)
3. Opens SFSafariViewController with new URL

No caching — links expire in 5 minutes.

### Status Polling

Status checked:
- On view appear (`.task`)
- After Safari dismissal (`.onDisappear`)
- On retry (failed state)

Status determines UI state:
- Not set up → show setup button
- Pending verification → show "complete" button + info
- Active → allow progression + show manage button

### Profile Reload After Setup

When Safari dismissed and status is active:
```swift
await appState.loadContractorProfile()
```

Updates `contractorProfile.stripeConnectId` → changes `hasCompletedStripeConnect` → allows progression to main app.

## Deviations from Plan

None — plan executed exactly as written.

## Testing Notes

All UI elements use driver design system:
- `DriverSpacing` for consistent padding
- `DriverTypography` for text styles
- `Color.driverPrimary`, `Color.driverSuccess`, `Color.driverWarning`, `Color.driverError`
- `DriverPrimaryButtonStyle` for action buttons
- `.driverCard()` modifier for card containers

Status badges follow driver app pattern:
- Circle background with opacity
- System icon (exclamationmark.triangle / clock / checkmark.circle)
- Color-coded by state

## Key Files Modified

**JunkOS-Driver/ViewModels/StripeConnectViewModel.swift** (NEW, +86 lines)
- Observable ViewModel with status enum
- checkStatus, startOnboarding, onSafariDismissed methods
- Fresh link generation pattern

**JunkOS-Driver/Views/Auth/StripeConnectOnboardingView.swift** (NEW, +171 lines)
- Mandatory full-screen setup gate
- Status-driven UI with badges
- SafariView UIViewControllerRepresentable wrapper

**JunkOS-Driver/Services/DriverAPIClient.swift** (+60 lines)
- 3 new Connect API methods
- 3 new response model structs with CodingKeys

**JunkOS-Driver/ViewModels/AppState.swift** (+1 line)
- hasCompletedStripeConnect computed property

**JunkOS-Driver/JunkOSDriverApp.swift** (+2 lines)
- Connect gate condition before main tab view

**JunkOS-Driver/Views/Profile/PayoutSettingsView.swift** (-166 lines, +251 lines)
- Replaced manual bank form with Connect status UI
- Status card with badges
- Action buttons per status state
- "How payouts work" info section

## Next Steps (Plan 03-04)

Already complete — earnings dashboard with history list.

## Verification Results

✅ StripeConnectOnboardingView blocks app access until Connect complete
✅ JunkOSDriverApp has Connect gate after registration, before main tabs
✅ PayoutSettingsView shows status badge, no manual bank form
✅ SFSafariViewController used for all Stripe Connect web flows
✅ Account links generated fresh on each tap (not cached)
✅ AppState.hasCompletedStripeConnect derives from contractor profile

## Self-Check

**Created files:**
- ✅ JunkOS-Driver/ViewModels/StripeConnectViewModel.swift exists
- ✅ JunkOS-Driver/Views/Auth/StripeConnectOnboardingView.swift exists

**Modified files:**
- ✅ JunkOS-Driver/Services/DriverAPIClient.swift exists and modified
- ✅ JunkOS-Driver/ViewModels/AppState.swift exists and modified
- ✅ JunkOS-Driver/JunkOSDriverApp.swift exists and modified
- ✅ JunkOS-Driver/Views/Profile/PayoutSettingsView.swift exists and modified

**Commits:**
- ✅ 23c07f1 (Task 1: Mandatory Stripe Connect onboarding gate)
- ✅ 5014edd (Task 2: Replace PayoutSettingsView with Connect status)

## Self-Check: PASSED

All files created and modified as expected. All commits present in git history.
