---
phase: 06-real-time-tracking
plan: 01
subsystem: real-time, tracking, notifications
tags: socket.io, gps, location, apns, push-notifications, core-location

# Dependency graph
requires:
  - phase: 04-dispatch-system
    provides: Socket.IO infrastructure and real-time job updates
  - phase: 05-volume-adjustment
    provides: Push notification delivery with APNs integration
provides:
  - Driver GPS streaming via Socket.IO during active jobs (en_route through started)
  - Complete push notification coverage for all 4 job status transitions
  - Throttled location updates (5s interval, 20m distance filter) for battery optimization
affects: [07-customer-tracking, real-time-features]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Location streaming tied to job status lifecycle (start on en_route, stop on completed)"
    - "Throttled GPS emission with time-based interval and distance filter"
    - "Battery-optimized location accuracy (NearestTenMeters vs Best)"

key-files:
  created: []
  modified:
    - "JunkOS-Driver/Managers/LocationManager.swift"
    - "JunkOS-Driver/ViewModels/ActiveJobViewModel.swift"
    - "backend/routes/drivers.py"

key-decisions:
  - "Use kCLLocationAccuracyNearestTenMeters instead of Best for battery optimization"
  - "5-second emit interval with 20m distance filter balances real-time updates and battery life"
  - "Location streaming lifecycle tied to job status (en_route starts, completed stops)"
  - "Category field added to all push notifications for deep linking consistency"

patterns-established:
  - "Location streaming controlled by ActiveJobViewModel tied to status transitions"
  - "Separate LocationManager instances per context (AppState for general, ActiveJobViewModel for job-specific)"
  - "All push notifications include category field for deep linking and notification grouping"

# Metrics
duration: 4.5min
completed: 2026-02-14
---

# Phase 06 Plan 01: Driver GPS Streaming & Complete Push Notification Coverage

**Driver app streams throttled GPS via Socket.IO during active jobs with 5s/20m filtering, backend sends push notifications for all 4 status transitions (en_route, arrived, started, completed)**

## Performance

- **Duration:** 4.5 min
- **Started:** 2026-02-14T14:51:28Z
- **Completed:** 2026-02-14T14:56:17Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Driver location streams to backend every 5 seconds via Socket.IO when job is en_route, arrived, or started
- Customer receives APNs push notification for each of the 4 job status transitions
- Battery-optimized location tracking with NearestTenMeters accuracy and 20m distance filter
- Location streaming lifecycle automatically managed by job status transitions

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire driver location streaming during active jobs** - `3c62f34` (feat)
2. **Task 2: Add push notifications for arrived and started status transitions** - `4bcccfd` (feat)

## Files Created/Modified
- `JunkOS-Driver/Managers/LocationManager.swift` - Added throttled GPS emission with 5s interval and 20m distance filter, activeJobId/contractorId context for streaming, startActiveJobTracking/stopActiveJobTracking lifecycle methods, changed accuracy from Best to NearestTenMeters
- `JunkOS-Driver/ViewModels/ActiveJobViewModel.swift` - Added LocationManager instance, starts streaming on en_route status, stops on completed status
- `backend/routes/drivers.py` - Added push notifications for arrived and started status transitions, added category field to all 4 status push notifications (en_route, arrived, started, completed)

## Decisions Made
- Used `kCLLocationAccuracyNearestTenMeters` instead of `kCLLocationAccuracyBest` for battery optimization (per research guidance)
- Set `distanceFilter = 20` to reduce unnecessary location updates when driver hasn't moved significantly
- 5-second throttle interval balances real-time tracking needs with battery consumption
- Added category field to all push notifications for consistent deep linking support
- Location streaming lifecycle tied to job status: starts on en_route transition, stops on completed transition
- Used job's `driverId` property instead of Keychain for contractor ID (more reliable, already available in response)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Driver GPS streaming ready for customer real-time map view integration
- All status push notifications firing correctly, ready for customer app notification handling
- Socket.IO infrastructure tested and working for location updates
- Battery-optimized location settings established as pattern for future location features

## Self-Check: PASSED

All files verified:
- ✓ JunkOS-Driver/Managers/LocationManager.swift exists and contains throttling logic
- ✓ JunkOS-Driver/ViewModels/ActiveJobViewModel.swift exists and contains status lifecycle management
- ✓ backend/routes/drivers.py exists and contains all 4 status push notifications

All commits verified:
- ✓ 3c62f34 exists (Task 1: Driver location streaming)
- ✓ 4bcccfd exists (Task 2: Push notifications)

---
*Phase: 06-real-time-tracking*
*Completed: 2026-02-14*
