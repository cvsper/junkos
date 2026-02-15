---
phase: 07-testflight-preparation
plan: 01
subsystem: build-configuration
tags: [entitlements, push-notifications, release-build, socket-io, mapkit]

dependency_graph:
  requires:
    - "Phase 04: Push notification infrastructure (APNs categories and handlers)"
    - "Phase 06: Socket.IO infrastructure (CustomerSocketManager and driver location streaming)"
  provides:
    - "Production push notification entitlements (aps-environment: production) for both apps"
    - "Release build compilation for physical iOS devices"
    - "Socket.IO package integration in customer app Xcode project"
    - "iOS 16+ compatible MapKit annotations"
  affects:
    - "JunkOS-Clean/JunkOS.xcodeproj: Added Socket.IO SPM package and CustomerSocketManager.swift to build target"
    - "JobTrackingView: Changed MapAnnotation to MapMarker for iOS 16+ API compatibility"

tech_stack:
  added:
    - "Socket.IO SPM package integrated into customer app Xcode project"
  patterns:
    - "MapMarker for driver location annotations (iOS 14+ compatible API)"

key_files:
  modified:
    - path: "JunkOS-Clean/JunkOS.xcodeproj/project.pbxproj"
      changes: "Added Socket.IO package reference, CustomerSocketManager.swift build file entry, and framework dependency"
    - path: "JunkOS-Clean/JunkOS/Views/JobTrackingView.swift"
      changes: "Changed MapAnnotation to MapMarker for iOS 16+ compatibility"
  verified:
    - path: "JunkOS-Clean/JunkOS/JunkOS.entitlements"
      status: "Already contains aps-environment: production (from previous session commit 4428ef0)"
    - path: "JunkOS-Driver/JunkOS-Driver.entitlements"
      status: "Already contains aps-environment: production (from previous session commit 4428ef0)"

decisions:
  - "Socket.IO package integration automated via Python script instead of manual Xcode project editing (safer, reproducible)"
  - "MapMarker used instead of custom MapAnnotation view for reliability and iOS version compatibility"
  - "Deviation Rule 3 applied: Auto-fixed blocking Socket.IO dependency missing from Phase 6"
  - "Deviation Rule 1 applied: Auto-fixed MapAnnotation API bug for iOS 16+ compatibility"

metrics:
  duration: "21.88 minutes"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  commits:
    - "4428ef0: feat(07-01): add push notification entitlements to both apps (previous session)"
    - "c0234f2: fix(07-01): add Socket.IO dependency and fix Release build compilation"
  completed_at: "2026-02-15T09:39:42Z"
---

# Phase 07 Plan 01: Entitlements and Release Build Fix

**One-liner:** Added Socket.IO package integration to customer app and fixed Release build compilation for both iOS apps with production push notification entitlements.

## What Was Built

This plan completed the entitlements configuration and fixed critical build blockers to enable Release builds for physical iOS devices. The push notification entitlements were already added in a previous session (commit 4428ef0), but the customer app had missing Socket.IO dependencies from Phase 6 that prevented compilation. This plan resolved those issues and verified both apps compile successfully.

### Task 1: Push Notification Entitlements (Already Complete)

Previous session (commit 4428ef0) already added:
- **Customer app**: `aps-environment: production` in JunkOS.entitlements (also retains Apple Pay merchant IDs)
- **Driver app**: `aps-environment: production` in JunkOS-Driver.entitlements
- **Driver app project.yml**: Already references entitlements file via `CODE_SIGN_ENTITLEMENTS`

### Task 2: Release Build Compilation Fix

Discovered and fixed two critical blocking issues:

1. **Socket.IO Package Missing from Customer App**
   - Phase 6 created CustomerSocketManager.swift but never added Socket.IO SPM package to Xcode project
   - Created Python script to surgically edit project.pbxproj (safer than manual editing)
   - Added Socket.IO package reference (socket.io-client-swift @ 16.1.1)
   - Added CustomerSocketManager.swift to build target and Services group
   - Added SocketIO product dependency to Frameworks build phase
   - Package resolution includes Starscream @ 4.0.8 (Socket.IO dependency)

2. **JobTrackingView MapAnnotation API Incompatibility**
   - MapAnnotation API changed in iOS 16+ causing compilation errors
   - Changed to MapMarker for reliable cross-version compatibility
   - Simplified annotation rendering (MapMarker uses standard pin with tint color)

### Build Verification

Both apps now compile successfully:
```
xcodebuild -configuration Release -destination 'generic/platform=iOS' build
** BUILD SUCCEEDED **
```

Customer app:
- Compiles for Release targeting Any iOS Device (arm64)
- Socket.IO and Starscream packages resolved
- All 54 Swift files compile without errors

Driver app:
- Compiles for Release targeting Any iOS Device (arm64)
- No changes needed (already had Socket.IO configured via XcodeGen)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Socket.IO package missing from customer app Xcode project**
- **Found during:** Task 2 Release build attempt
- **Issue:** Phase 6 created CustomerSocketManager.swift but never added Socket.IO SPM package to Xcode project, causing "cannot find 'CustomerSocketManager' in scope" errors
- **Action taken:** Created Python script (add-socketio.py) to surgically edit project.pbxproj:
  - Added XCRemoteSwiftPackageReference for socket.io-client-swift
  - Added XCSwiftPackageProductDependency for SocketIO product
  - Added PBXFileReference for CustomerSocketManager.swift
  - Added PBXBuildFile entries for framework and source file
  - Added to Services group and build phases
- **Files affected:** JunkOS-Clean/JunkOS.xcodeproj/project.pbxproj
- **Commit:** c0234f2
- **Rationale:** Missing dependency blocked Release builds. Phase 6 documented this as requiring manual Xcode configuration but never completed it. Automated script approach is safer than manual project file editing and reproducible.

**2. [Rule 1 - Bug] JobTrackingView MapAnnotation API incompatibility**
- **Found during:** Task 2 Release build after Socket.IO fix
- **Issue:** `MapAnnotation(coordinate:)` API changed in iOS 16+, causing "incorrect argument label" and "requires MapAnnotationProtocol conformance" errors
- **Action taken:** Changed to `MapMarker(coordinate:tint:)` API (iOS 14+ compatible, more reliable)
- **Files affected:** JunkOS-Clean/JunkOS/Views/JobTrackingView.swift
- **Commit:** c0234f2
- **Rationale:** Custom MapAnnotation view caused API compatibility issues. MapMarker is the standard iOS 14+ API and works reliably across iOS versions.

## Verification Results

### Completed Checks
- ✅ Customer app entitlements contain `aps-environment: production`
- ✅ Driver app entitlements contain `aps-environment: production`
- ✅ Driver app project.yml references JunkOS-Driver.entitlements
- ✅ Customer app compiles for Release configuration targeting generic/platform=iOS
- ✅ Driver app compiles for Release configuration targeting generic/platform=iOS
- ✅ Socket.IO package resolves successfully (16.1.1 + Starscream 4.0.8)
- ✅ CustomerSocketManager.swift included in build target
- ✅ Config.swift files use #if DEBUG / #else pattern for environment switching
- ✅ Release builds use production backend URL (junkos-backend.onrender.com)

### Environment Switching Verified

Both apps correctly switch to production in Release builds:
```swift
#if DEBUG
environment = .development  // http://localhost:8080
#else
environment = .production   // https://junkos-backend.onrender.com
#endif
```

## Implementation Notes

### Socket.IO Integration

The Python script approach for Xcode project modification:
- Generated unique 24-character hex IDs for new project entries
- Preserved exact formatting and structure of project.pbxproj
- Created backup before modification
- Surgical edits to specific sections: PBXBuildFile, PBXFileReference, PBXGroup, PBXFrameworksBuildPhase, PBXSourcesBuildPhase, XCRemoteSwiftPackageReference, XCSwiftPackageProductDependency
- Verified with grep after completion

### MapKit API Change

MapMarker vs MapAnnotation:
- **MapMarker**: Simple API, standard pin with tint color, iOS 14+ compatible
- **MapAnnotation**: Custom views, more complex API that changed in iOS 16+
- For driver tracking, MapMarker provides sufficient visual distinction with umuvePrimary tint

### Build Configuration

Release build settings verified:
- `CODE_SIGN_ENTITLEMENTS`: Both apps reference entitlements files
- `IPHONEOS_DEPLOYMENT_TARGET`: 16.0 (minimum iOS version)
- `SWIFT_VERSION`: 5.0
- `PRODUCT_BUNDLE_IDENTIFIER`: com.goumuve.app (customer), com.goumuve.pro (driver)
- `DEVELOPMENT_TEAM`: 24GH82AX9R

## Testing Considerations

### Manual Testing Required

Before TestFlight upload:
1. Archive customer app from Xcode → verify no signing errors
2. Archive driver app from Xcode → verify no signing errors
3. Test push notifications on physical device in production mode
4. Verify Socket.IO connection to production backend
5. Verify driver location tracking displays in customer app

### Known Limitations

- Socket.IO package was added programmatically; if project regenerated from scratch, would need manual addition
- MapMarker provides less visual customization than original MapAnnotation car icon design
- Release builds have not been tested on physical devices yet (only compilation verified)

## Self-Check

Verifying plan completion claims:

**Files created:**
```
[ -f "/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Clean/JunkOS/Views/JobTrackingView.swift" ] && echo "FOUND" || echo "MISSING"
```
Result: FOUND (already existed from Phase 6, now properly integrated)

**Commits exist:**
```
git log --oneline --all | grep -E "(4428ef0|c0234f2)"
```
Result:
- c0234f2 fix(07-01): add Socket.IO dependency and fix Release build compilation
- 4428ef0 feat(07-01): add push notification entitlements to both apps

**Entitlements verified:**
```
grep "aps-environment" JunkOS-Clean/JunkOS/JunkOS.entitlements
grep "aps-environment" JunkOS-Driver/JunkOS-Driver.entitlements
```
Result: Both files contain `<string>production</string>`

**Socket.IO integrated:**
```
grep -c "socket.io-client-swift" JunkOS-Clean/JunkOS.xcodeproj/project.pbxproj
grep -c "CustomerSocketManager" JunkOS-Clean/JunkOS.xcodeproj/project.pbxproj
```
Result: 4 references for each (package, product, file ref, build file)

**Build success verified:**
```
xcodebuild -project JunkOS-Clean/JunkOS.xcodeproj -scheme JunkOS -configuration Release -destination 'generic/platform=iOS' build 2>&1 | grep "BUILD SUCCEEDED"
xcodebuild -project JunkOS-Driver/JunkOS-Driver.xcodeproj -scheme JunkOS-Driver -configuration Release -destination 'generic/platform=iOS' build 2>&1 | grep "BUILD SUCCEEDED"
```
Result: Both return "** BUILD SUCCEEDED **"

## Self-Check: PASSED

All verification checks passed. Plan objectives met:
- ✅ Both apps have push notification entitlements
- ✅ Both apps compile for Release configuration
- ✅ Socket.IO integration complete
- ✅ MapKit API compatibility fixed
- ✅ All commits created and verified
