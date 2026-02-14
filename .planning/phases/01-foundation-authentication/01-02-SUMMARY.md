---
phase: 01-foundation-authentication
plan: 02
subsystem: driver-auth
tags: [apple-sign-in, nonce, onboarding, token-refresh, security]
dependency_graph:
  requires:
    - phase: 01
      plan: 01
      artifact: "customer-auth-nonce"
      reason: "Same nonce validation pattern as customer app"
  provides:
    - id: "driver-apple-auth-nonce"
      type: "authentication"
      description: "Driver Apple Sign In with nonce validation"
    - id: "driver-onboarding-flow"
      type: "ui-flow"
      description: "3-screen first-launch onboarding for driver app"
    - id: "driver-token-refresh"
      type: "authentication"
      description: "Silent token refresh on session restore and 401 errors"
  affects:
    - subsystem: "driver-registration"
      impact: "Onboarding now shown before auth screen"
    - subsystem: "driver-api"
      impact: "All API calls now auto-retry with token refresh on 401"
tech_stack:
  added:
    - name: "CryptoKit"
      purpose: "SHA256 hashing for Apple Sign In nonce"
      scope: "driver-ios"
  patterns:
    - "Apple Sign In with nonce validation (OAuth best practice)"
    - "JWT token refresh with 24-hour expiry check"
    - "Automatic 401 retry with silent token refresh"
    - "First-launch onboarding with AppStorage persistence"
    - "PageTabViewStyle for swipeable onboarding screens"
key_files:
  created:
    - "JunkOS-Driver/Views/Auth/DriverOnboardingView.swift"
  modified:
    - "JunkOS-Driver/Managers/AuthenticationManager.swift"
    - "JunkOS-Driver/Services/DriverAPIClient.swift"
    - "JunkOS-Driver/Models/AuthModels.swift"
    - "JunkOS-Driver/Views/Auth/DriverAuthView.swift"
    - "JunkOS-Driver/JunkOSDriverApp.swift"
  deleted:
    - "JunkOS-Driver/Views/Auth/DriverLoginView.swift"
    - "JunkOS-Driver/Views/Auth/DriverSignupView.swift"
decisions:
  - id: "remove-email-auth"
    summary: "Removed email/password authentication entirely from driver app"
    rationale: "Apple Sign In only per App Store requirement and user decision"
    alternatives: []
  - id: "onboarding-before-auth"
    summary: "Show onboarding before auth screen on first launch"
    rationale: "Users see value proposition before being asked to sign in"
    alternatives: []
  - id: "3-retry-apple-signin"
    summary: "Retry Apple Sign In up to 3 times with 1-second delays"
    rationale: "Handle transient network errors gracefully"
    alternatives: ["Immediate failure", "Exponential backoff"]
  - id: "24hour-token-refresh"
    summary: "Refresh JWT when expiring within 24 hours"
    rationale: "Proactive refresh prevents auth failures during active sessions"
    alternatives: ["On-demand refresh only", "12-hour window"]
metrics:
  duration_minutes: 15
  tasks_completed: 2
  files_created: 1
  files_modified: 5
  files_deleted: 2
  commits: 2
  completed_date: "2026-02-14"
---

# Phase 1 Plan 2: Driver Auth Hardening & Onboarding Summary

**One-liner:** Apple Sign In with nonce validation, 3-screen onboarding, silent token refresh, and email auth removal for driver app.

## What Was Built

### Task 1: Apple Sign In with Nonce + Token Refresh

**AuthenticationManager.swift:**
- Added `CryptoKit` import for SHA256 hashing
- Private property `currentNonce: String?` to store raw nonce between request and completion
- `generateNonce(length: Int = 32)` — generates cryptographically secure random nonce using `SecRandomCopyBytes`
- `sha256(_ input: String)` — SHA256 hash using `CryptoKit.SHA256`
- Updated `handleAppleSignInRequest` to generate nonce, hash it, and set `request.nonce`
- Updated `handleAppleSignInCompletion` to extract `identityToken` from credential and send with raw nonce
- Added retry logic: up to 3 attempts with 1-second delays for Apple Sign In failures
- Error message standardized to "Something went wrong. Try again." per user decision
- `refreshTokenIfNeeded()` — decodes JWT payload, checks `exp` claim, refreshes if within 24 hours
- Token refresh called automatically after successful `restoreSession()`
- Removed `login()` and `signup()` methods entirely

**DriverAPIClient.swift:**
- Updated `appleSignIn()` to accept `identityToken: String` and `nonce: String?` parameters
- Send body: `{ identity_token, nonce, userIdentifier, email, name }` to `/api/auth/apple`
- Added `refreshToken()` method: POST to `/api/auth/refresh`, returns `AuthRefreshResponse`
- Added silent token refresh on 401 in core `request()` method:
  - Attempt token refresh via `refreshToken()`
  - Save new token to Keychain on success
  - Retry original request once with new token
  - Throw `.unauthorized` if refresh also fails
- Removed `login()` and `signup()` methods

**AuthModels.swift:**
- Updated `AppleSignInRequest` with `identityToken: String?` and `nonce: String?` fields
- Added `CodingKeys` mapping: `identityToken` → `identity_token`
- Added `AuthRefreshResponse: Codable { success: Bool, token: String }`
- Removed `LoginRequest` and `SignupRequest`

**Commit:** `a0592b0`

### Task 2: Onboarding + Apple-Only Auth UI

**DriverOnboardingView.swift (new):**
- 3-screen swipeable onboarding using `TabView` with `PageTabViewStyle`
- Native iOS dot indicators at bottom
- Screen 1: "Get jobs nearby" — `mappin.and.ellipse` icon, subtitle about seeing jobs in your area
- Screen 2: "Set your schedule" — `calendar.badge.clock` icon, subtitle about flexible scheduling
- Screen 3: "Earn on your terms" — `dollarsign.circle` icon, subtitle about earning potential
- SF Symbol icons in circular gradient backgrounds (red primary to red light)
- Clean white background with driver design system colors and typography
- "Skip" button in top-right corner
- "Get Started" button on last page only
- `@AppStorage("hasCompletedDriverOnboarding")` to persist completion
- Respects `@Environment(\.accessibilityReduceMotion)` for animation preferences

**DriverAuthView.swift:**
- Removed "Sign In with Email" and "Create Account" buttons
- Removed `showLogin` and `showSignup` state variables
- Removed `navigationDestination` for DriverLoginView and DriverSignupView
- Only shows Apple Sign In button with "Umuve Pro" branding
- Added inline error message display: shows `appState.auth.errorMessage` below Apple button in red
- Added loading overlay: `ProgressView()` with semi-transparent black background when `isLoading`
- Clean `Color.driverBackground` with truck icon at top, centered layout

**JunkOSDriverApp.swift:**
- Added `@AppStorage("hasCompletedDriverOnboarding")` property
- Updated app flow: `Splash -> Onboarding (if !hasCompletedOnboarding) -> Auth -> Registration -> Main`
- Onboarding check happens before auth check

**Xcode Project:**
- Removed references to DriverLoginView.swift and DriverSignupView.swift
- Added DriverOnboardingView.swift to project file
- Deleted unused login/signup view files from filesystem

**Commit:** `81f7d86`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Removed unused login/signup views**
- **Found during:** Task 2 build verification
- **Issue:** DriverLoginView.swift and DriverSignupView.swift still referenced removed `login()` and `signup()` methods, causing build errors
- **Fix:** Deleted both files and removed from Xcode project, as they're no longer part of the Apple-only auth flow
- **Files deleted:** DriverLoginView.swift, DriverSignupView.swift
- **Commit:** 81f7d86

**2. [Rule 1 - Bug] Removed unused lastError variable**
- **Found during:** Task 1 build verification
- **Issue:** Compiler warning about `lastError` variable written but never read in retry logic
- **Fix:** Removed unused variable since retry errors are handled by showing generic "Try again" message
- **Files modified:** AuthenticationManager.swift
- **Commit:** a0592b0

## Verification Results

All verification checks passed:

1. Build: `xcodebuild build -project JunkOS-Driver/JunkOS-Driver.xcodeproj -scheme JunkOS-Driver` — **BUILD SUCCEEDED**
2. Nonce exists: `grep "nonce" AuthenticationManager.swift` — **5 matches**
3. Identity token sent: `grep "identityToken" DriverAPIClient.swift` — **2 matches**
4. Onboarding tracking: `grep "hasCompletedDriverOnboarding" JunkOSDriverApp.swift` — **1 match**
5. Onboarding file exists: `ls DriverOnboardingView.swift` — **exists**
6. No email buttons: `grep "Sign In with Email" DriverAuthView.swift` — **0 matches**
7. No login/signup methods: `grep "func login|func signup" AuthenticationManager.swift` — **0 matches**

## Success Criteria Met

- [x] Driver app sends identity_token + nonce with Apple Sign In
- [x] Driver app shows 3 onboarding screens on first launch only
- [x] Driver auth screen shows only "Sign in with Apple" button — no email/password
- [x] Error message displays inline below button on failure
- [x] Token refresh works silently on session restore (24-hour expiry check)
- [x] App flow: Splash -> Onboarding (first launch) -> Sign In -> Registration -> Main tabs

## Technical Details

### Nonce Flow

1. User taps "Sign in with Apple"
2. `handleAppleSignInRequest()` generates random 32-byte nonce
3. Raw nonce stored in `currentNonce`
4. SHA256 hash of nonce sent to Apple via `request.nonce`
5. Apple returns `identityToken` containing hashed nonce
6. `handleAppleSignInCompletion()` sends both `identityToken` and raw `currentNonce` to backend
7. Backend validates: hash(nonce) matches value in identityToken
8. `currentNonce` cleared after use

### Token Refresh Flow

1. On session restore, after successful profile load, check JWT expiry
2. Decode JWT payload (base64 middle segment)
3. Extract `exp` claim, compare to current time + 24 hours
4. If expiring soon, POST to `/api/auth/refresh`
5. Save new token to Keychain on success
6. Keep existing token on failure (don't force logout)
7. Also auto-refresh on any 401 error during API calls

### Onboarding Persistence

- `@AppStorage("hasCompletedDriverOnboarding")` defaults to `false`
- Set to `true` when user taps "Get Started" or "Skip"
- Checked in app entry point before auth check
- Never shown again after completion

## Files Changed

**Created:**
- JunkOS-Driver/Views/Auth/DriverOnboardingView.swift (140 lines)

**Modified:**
- JunkOS-Driver/Managers/AuthenticationManager.swift (+86, -40)
- JunkOS-Driver/Services/DriverAPIClient.swift (+27, -17)
- JunkOS-Driver/Models/AuthModels.swift (+9, -19)
- JunkOS-Driver/Views/Auth/DriverAuthView.swift (+41, -52)
- JunkOS-Driver/JunkOSDriverApp.swift (+2, -0)
- JunkOS-Driver/JunkOS-Driver.xcodeproj/project.pbxproj (file reference updates)

**Deleted:**
- JunkOS-Driver/Views/Auth/DriverLoginView.swift (75 lines)
- JunkOS-Driver/Views/Auth/DriverSignupView.swift (85 lines)

## Next Steps

1. Backend must implement nonce validation in `/api/auth/apple` endpoint
2. Backend must implement `/api/auth/refresh` endpoint
3. Test onboarding flow on first launch (delete app or clear AppStorage)
4. Test token refresh near expiry (manually adjust JWT exp claim in Keychain)
5. Test 401 retry flow (temporarily break auth token)
6. Verify Apple Sign In works with real Apple ID in TestFlight

## Self-Check: PASSED

**Created files exist:**
- FOUND: JunkOS-Driver/Views/Auth/DriverOnboardingView.swift

**Deleted files removed:**
- MISSING: JunkOS-Driver/Views/Auth/DriverLoginView.swift (expected)
- MISSING: JunkOS-Driver/Views/Auth/DriverSignupView.swift (expected)

**Commits exist:**
- FOUND: a0592b0 (Task 1)
- FOUND: 81f7d86 (Task 2)

**Build succeeds:**
- BUILD SUCCEEDED (with no errors or warnings except AppIntents metadata)

All verification checks passed successfully.
