---
phase: 07-testflight-preparation
plan: 03
subsystem: testflight-validation
tags: [backend-verification, apple-sign-in, app-icons, testflight, physical-device]

dependency_graph:
  requires:
    - "07-01: Release build compilation and entitlements"
    - "07-02: Privacy policy and App Store metadata"
  provides:
    - "Production backend connectivity verification"
    - "Sign in with Apple entitlement fix for both apps"
    - "Umuve logo app icons for both apps"
    - "Both apps uploaded to App Store Connect"
  affects:
    - "JunkOS-Clean/JunkOS/JunkOS.entitlements: Added com.apple.developer.applesignin"
    - "JunkOS-Driver/JunkOS-Driver.entitlements: Added com.apple.developer.applesignin"
    - "Both apps AppIcon.appiconset: Replaced with Umuve logo"

key_files:
  modified:
    - path: "JunkOS-Clean/JunkOS/JunkOS.entitlements"
      changes: "Added Sign in with Apple entitlement (com.apple.developer.applesignin)"
    - path: "JunkOS-Driver/JunkOS-Driver.entitlements"
      changes: "Added Sign in with Apple entitlement (com.apple.developer.applesignin)"
    - path: "JunkOS-Clean/JunkOS/Assets.xcassets/AppIcon.appiconset/"
      changes: "Replaced all icon sizes with Umuve logo (umuvelogoWhite.png)"
    - path: "JunkOS-Driver/Assets.xcassets/AppIcon.appiconset/"
      changes: "Replaced all icon sizes with Umuve logo (umuvelogoWhite.png)"

decisions:
  - "Sign in with Apple entitlement was missing from Phase 1 implementation — added now as critical fix"
  - "Used umuvelogoWhite.png (1024x1024 red U with truck) as source for all app icon sizes"
  - "Both apps icons are identical (same Umuve brand) — driver app could be differentiated later"

metrics:
  duration: "~8 minutes"
  tasks_completed: 2
  files_modified: 28
  commits:
    - "cac4945: fix(07-03): add Sign in with Apple entitlement and Umuve logo app icons"
  completed_at: "2026-02-15"
---

# Phase 07 Plan 03: Production Backend Testing & TestFlight Upload

**One-liner:** Verified production backend connectivity, fixed missing Sign in with Apple entitlement, replaced app icons with Umuve logo, and both apps uploaded to App Store Connect.

## What Was Built

### Task 1: Production Backend Verification

Tested production backend at `junkos-backend.onrender.com`:
- Auth endpoint (`/api/auth/apple`): Returns 400 with validation error (endpoint exists, validates input)
- Jobs endpoint (`/api/jobs`): Returns 401 Unauthorized (auth layer working correctly)
- Socket.IO endpoint: Responding with protocol message (real-time infrastructure active)
- Backend is live and accepting requests

### Task 2: Physical Device Testing & App Store Connect Upload (Human Checkpoint)

User tested both apps and uploaded to App Store Connect. During testing, two issues were identified and fixed:

**Issue 1: Sign in with Apple Not Working**
- Root cause: `com.apple.developer.applesignin` entitlement was missing from both apps
- This was never added in Phase 1 when Apple Sign In was implemented
- Fixed by adding the entitlement to both `JunkOS.entitlements` and `JunkOS-Driver.entitlements`

**Issue 2: App Icons Were Generic Placeholders**
- Both apps had script-generated placeholder icons instead of the actual Umuve logo
- Replaced all 13 icon sizes (20px to 1024px) in both apps with the Umuve logo
- Source: `umuvelogoWhite.png` (1024x1024, red U with truck on white background)

## Verification Results

- ✅ Production backend responding to HTTP requests
- ✅ Auth endpoint validates input (400, not 404/500)
- ✅ Jobs endpoint requires authentication (401)
- ✅ Socket.IO endpoint active
- ✅ Sign in with Apple entitlement added to both apps
- ✅ Umuve logo app icons in both apps (all 13 sizes)
- ✅ Both apps built and uploaded to App Store Connect (user confirmed)

## Self-Check: PASSED
