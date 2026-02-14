---
phase: 01-foundation-authentication
plan: 03
subsystem: customer-app-ui
tags: [onboarding, apple-sign-in, ui, routing, auth-flow]
dependency-graph:
  requires: [01-01]
  provides: [customer-onboarding-flow, apple-only-sign-in-ui, sign-out-ui]
  affects: [app-entry-point, profile-view]
tech-stack:
  added: [Network-framework, NWPathMonitor]
  patterns: [swipeable-onboarding, auth-gate-routing, offline-detection]
key-files:
  created: []
  modified:
    - JunkOS-Clean/JunkOS/Components/Onboarding/OnboardingView.swift
    - JunkOS-Clean/JunkOS/Views/Auth/WelcomeAuthView.swift
    - JunkOS-Clean/JunkOS/JunkOSApp.swift
    - JunkOS-Clean/JunkOS/Views/ProfileView.swift
    - JunkOS-Clean/JunkOS/Views/EnhancedWelcomeView.swift
    - JunkOS-Clean/JunkOS/Views/WelcomeView.swift
decisions:
  - "Use PageTabViewStyle for native iOS swipeable onboarding with dots indicator"
  - "Remove OnboardingManager class — use @AppStorage directly for simplicity"
  - "Deprecate EnhancedWelcomeView instead of deleting to preserve Xcode project references"
  - "Use NWPathMonitor for offline detection with animated banner overlay"
  - "Add sign-out confirmation alert to prevent accidental logouts"
metrics:
  duration: 5
  completed: 2026-02-14T01:51:02Z
---

# Phase 01 Plan 03: Customer Onboarding and Apple Sign In UI Summary

3-screen customer onboarding flow with Apple Sign In only, no guest/phone/email auth

## Tasks Completed

### Task 1: Rewrite customer onboarding and Apple-only sign-in screen
**Status:** Complete
**Commit:** 067c462

**OnboardingView.swift** — Complete rewrite with 3-screen swipeable flow:
- Screen 1: "Book a pickup" — SF Symbol `shippingbox`, subtitle about hauling service
- Screen 2: "Track your driver" — SF Symbol `location.fill`, subtitle about real-time tracking
- Screen 3: "Done — hauling made simple" — SF Symbol `checkmark.circle`, subtitle about simplicity
- Uses `TabView` with `PageTabViewStyle(indexDisplayMode: .always)` for native iOS swipe + dots
- Clean white background (`Color.umuveBackground`), red accent circles for icons
- "Next" button for screens 1-2, "Get Started" on screen 3
- "Skip" text button in top-right corner
- Respects `@Environment(\.accessibilityReduceMotion)` — skips animations if enabled
- Removed `OnboardingManager` class — uses `@AppStorage("hasCompletedOnboarding")` directly
- Removed `PermissionPrePromptView` — not part of this phase

**WelcomeAuthView.swift** — Complete rewrite, Apple Sign In only:
- Clean white background (`Color.umuveBackground`) instead of gradient
- Umuve logo (SF Symbol `trash.circle.fill`) with red gradient + "Hauling made simple." tagline
- `SignInWithAppleButton(.signIn)` with `.black` style, 52pt height, clipped to rounded rectangle
- Calls `authManager.handleAppleSignInRequest(request)` and `authManager.handleAppleSignInCompletion(result)`
- Error message displays inline below button in `Color.umuveError` with `UmuveTypography.bodySmallFont`
- Loading state overlays `ProgressView()` on button area
- Removed ALL state variables: `showPhoneSignUp`, `showLogin`
- Removed ALL `fullScreenCover` for `PhoneSignUpView`, `LoginOptionsView`
- No guest mode, no phone signup, no email login

**WelcomeView.swift fix** — Removed `OnboardingManager` reference:
- Changed `@StateObject private var onboardingManager = OnboardingManager()` to `@AppStorage("hasCompletedOnboarding")`
- Updated `if !onboardingManager.hasCompletedOnboarding` to `if !hasCompletedOnboarding`

### Task 2: Rewire app entry point and add sign-out to profile
**Status:** Complete
**Commit:** 0166c6f

**JunkOSApp.swift** — Rewritten app entry point routing:
- Removed `showingSplash` state and `EnhancedWelcomeView` entirely
- Updated routing: `if !hasCompletedOnboarding { OnboardingView() } else if !authManager.isAuthenticated { WelcomeAuthView() } else { MainTabView() }`
- Auth wall: user must sign in before accessing any app content (no guest bypass)
- Added offline detection with `NWPathMonitor` from Network framework
- `@State private var isOffline = false` tracks network connectivity
- Offline banner overlay on MainTabView: "You're offline" with wifi.slash icon
- Banner auto-shows/hides with `.transition(.move(edge: .top).combined(with: .opacity))`
- Network monitor starts on `.onAppear`, updates `isOffline` on path changes
- Token refresh triggered on MainTabView appear: `Task { await authManager.refreshTokenIfNeeded() }`
- Removed `EnhancedWelcomeView` from routing flow

**EnhancedWelcomeView.swift** — Deprecated:
- Added comment at top: `// DEPRECATED: Replaced by OnboardingView.swift in Phase 1`
- File preserved to avoid breaking Xcode project references (still compiles but not used)

**ProfileView.swift** — Added sign-out button:
- `@EnvironmentObject var authManager: AuthenticationManager` for logout access
- `@State private var showSignOutConfirmation = false` for alert state
- New `signOutSection` at bottom with "Sign Out" button
- Style: red text on light red background (`Color.umuveError.opacity(0.1)`)
- On tap: shows confirmation alert "Are you sure you want to sign out?"
- Alert has "Cancel" (default) and "Sign Out" (destructive red) buttons
- Sign Out calls `Task { await authManager.logout() }` which clears Keychain and routes back to WelcomeAuthView

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed WelcomeView OnboardingManager reference**
- **Found during:** Task 1 build verification
- **Issue:** WelcomeView.swift still referenced `OnboardingManager` class after it was removed from OnboardingView
- **Fix:** Changed to use `@AppStorage("hasCompletedOnboarding")` directly
- **Files modified:** WelcomeView.swift
- **Commit:** 067c462

## Verification Results

### Success Criteria (All Met)

- [x] First launch shows 3 onboarding screens before sign-in (PageTabViewStyle with dots)
- [x] Sign-in screen has only Apple Sign In button — no guest, phone, or email options (0 matches for guest/phone/email in WelcomeAuthView)
- [x] User must authenticate before seeing any app content (auth wall in JunkOSApp routing)
- [x] Sign-out available in Profile view with confirmation (5 matches for "Sign Out|logout" in ProfileView)
- [x] Offline launch shows cached main view with offline banner (NWPathMonitor overlay)
- [x] App routing: Onboarding (once) -> Sign In -> Main (0 matches for "showingSplash|EnhancedWelcomeView" in JunkOSApp)

### Build Verification

```bash
xcodebuild build -project JunkOS-Clean/JunkOS.xcodeproj -scheme JunkOS \
  -destination 'platform=iOS Simulator,id=4FBDF7C0-BBBD-4B15-BBF7-8DE4D37AC754'
```
**Result:** BUILD SUCCEEDED (1 warning about duplicate WelcomeView.swift in Compile Sources, non-blocking)

### Grep Verification

- SignInWithAppleButton in WelcomeAuthView: 1 match
- guest/phone/email auth in WelcomeAuthView: 0 matches
- PageTabViewStyle in OnboardingView: 1 match
- hasCompletedOnboarding in JunkOSApp: 2 matches
- EnhancedWelcomeView|showingSplash in JunkOSApp: 0 matches
- continueAsGuest in JunkOSApp: 0 matches
- Sign Out|logout in ProfileView: 5 matches

## Self-Check

**Files Created:**
- None (all files modified)

**Commits Exist:**
- [x] FOUND: 067c462 (Task 1: Onboarding + Apple-only sign-in)
- [x] FOUND: 0166c6f (Task 2: App entry point + sign-out)

**Verification Checks:**
- [x] BUILD SUCCEEDED (Xcode build passed)
- [x] OnboardingView uses PageTabViewStyle (1 match)
- [x] WelcomeAuthView has SignInWithAppleButton (1 match)
- [x] WelcomeAuthView has no guest/phone/email (0 matches)
- [x] JunkOSApp routes via hasCompletedOnboarding (2 matches)
- [x] JunkOSApp has no splash screen (0 matches)
- [x] ProfileView has sign-out (5 matches)

## Self-Check: PASSED

All files modified, all commits present, all verification criteria met.

## Next Steps

Plan 01-04 (if exists): Continue phase 1 foundation work, OR move to Phase 2: booking flow UI/backend integration.
