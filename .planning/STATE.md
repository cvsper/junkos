# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A customer can book a junk hauling or auto transport job from their iPhone and a driver can accept and complete it — end-to-end, with real payments.
**Current focus:** Phase 6 - Real-Time Tracking

## Current Position

Phase: 6 of 7 (Real-Time Tracking)
Plan: 3 of 3
Status: Complete
Last activity: 2026-02-14 — Completed 06-03: Tracking view integration and end-to-end verification

Progress: [█████████░] 77%

## Performance Metrics

**Velocity:**
- Total plans completed: 22
- Average duration: 6.5 minutes
- Total execution time: ~143.95 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | ~40 min | ~13 min |
| 2 | 5 | ~54 min | ~10.8 min |
| 3 | 4 | ~6.8 min | ~1.7 min |
| 4 | 4 | ~21.5 min | ~5.4 min |
| 5 | 4 | ~10.3 min | ~2.6 min |
| 6 | 3 | ~13.96 min | ~4.65 min |

**Recent Trend:**
- 06-03: 3.65 minutes (2 tasks, tracking view integration and end-to-end verification)
- 06-02: 5.81 minutes (2 tasks, customer Socket.IO infrastructure and tracking map view)
- 06-01: 4.5 minutes (2 tasks, driver GPS streaming and complete push notification coverage)
- 05-04: 1.42 minutes (1 task, end-to-end volume adjustment verification)
- 05-03: 3.01 minutes (2 tasks, customer volume adjustment notifications)
- 05-02: 2.75 minutes (2 tasks, driver volume adjustment UI with Socket.IO listeners)
- 05-01: 3.15 minutes (2 tasks, volume adjustment workflow endpoints + APNs category support)
- 04-04: 3 minutes (1 task, end-to-end dispatch system verification)
- 04-02: 11.5 minutes (1 task, driver real-time job feed updates + Phase 3 build fixes)
- 04-03: 5 minutes (1 task, customer driver assignment notifications and status display)
- 04-01: 2 minutes (2 tasks, backend dispatch notifications with APNs + Socket.IO)
- 03-04: 2.5 minutes (2 tasks, driver earnings dashboard API integration)
- 03-03: 2.3 minutes (2 tasks, Stripe Connect onboarding + payout settings)
- 03-02: 2 minutes (2 tasks, Stripe Connect endpoints + earnings history API)
- 02-05: 5 minutes (2 tasks, review screen + job creation API)
- 02-04: 14 minutes (2 tasks, photos + schedule + pricing API integration)
- 02-03: 6 minutes (2 tasks, MapKit autocomplete address input)
- 02-02: 5 minutes (2 tasks, service type selection + wizard integration)
- 02-01: 24 minutes (2 tasks, data model refactor + wizard foundation + HomeView)
- 01-03: 5 minutes (2 tasks, onboarding + Apple-only sign-in UI)

*Updated after each plan completion*
| Phase 05 P03 | 3.01 | 2 tasks | 4 files |
| Phase 05 P04 | 1.42 | 1 tasks | 0 files |
| Phase 06 P01 | 4.5 | 2 tasks | 3 files |
| Phase 06 P03 | 3.65 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Apple Sign In only (no email/password on iOS) — App Store requirement, simplest auth UX
- Apple Maps / MapKit for distance + navigation — Free, native iOS, no API key costs
- Reverse auction + instant book dispatch — Market-driven pricing without manual dispatching
- 20% platform commission with Stripe Connect — Standard marketplace take, handles split payments
- Volume adjustment workflow with customer approval — Automated pricing with customer protection
- Trip fee on customer decline after driver arrives — Compensates driver for wasted time

**From Phase 1 (complete):**
- Use ObservableObject instead of @Observable for iOS 16 compatibility
- Cache Apple public keys for 24 hours to reduce API calls
- Support legacy userIdentifier flow for backward compatibility during transition
- 7-day grace period for token refresh to handle offline scenarios
- Use PageTabViewStyle for native iOS swipeable onboarding with dots indicator
- Use @AppStorage directly for onboarding state (no manager class)
- Use NWPathMonitor for offline detection with animated banner overlay
- Deprecate EnhancedWelcomeView instead of deleting to preserve Xcode project references

**From Phase 2 (complete):**
- 5-step wizard flow: Service → Address → Photos → Schedule → Review (data dependency order)
- Tappable progress dots enable free navigation to completed steps
- Running price estimate bar sticky at bottom with expandable line-item breakdown (hidden on review step)
- Temporary legacy properties in BookingData for backward compatibility during incremental refactor
- Each wizard step manages its own ScrollView to avoid nesting conflicts
- Single MKLocalSearchCompleter with searchMode enum for pickup/dropoff (simpler than two completers)
- 300ms debounce for autocomplete search to balance responsiveness and API efficiency
- Max 5 autocomplete suggestions to avoid overwhelming UI on mobile
- Horizontal bar blocks for truck fill visualization (simpler than custom illustrations)
- Photos are optional but encouraged (encouragement message shown when empty)
- Volume tier maps to item quantity for backend pricing API (quarter→2, half→5, threeQuarter→10, full→16)
- Pricing API calls are best-effort with silent failure (don't block user flow)
- Price estimate refreshes automatically when wizard step changes
- Upload photos first, then create job (sequential API calls for data integrity)
- Success overlay with job ID display instead of separate confirmation screen
- Mini-maps (MapKit) in review cards for visual address confirmation
- Wizard dismisses and resets on booking completion

**From Phase 3 (complete):**
- Earnings history shows driver_payout_amount only (80% take), not full job price — drivers see their earnings, not customer price
- Account links generated fresh every request, never cached — links expire in 5 minutes
- Connect status derived from Stripe API, not stored in DB — Stripe is source of truth for onboarding state
- Connect onboarding mandatory after registration, before main app access — drivers cannot reach job feed without payout method
- Status polling on view appear and Safari dismissal — Stripe onboarding is async, need to check for completion
- [Phase 03]: 4-segment date filter (today/week/month/all-time) with period-based earnings filtering
- [Phase 03]: Payout status badge colors: pending=amber, processing=blue, paid=green

**From Phase 4 (complete):**
- [Phase 04-01]: Lazy imports inside function bodies to avoid circular dependencies between routes and socket_events
- [Phase 04-01]: Separate Socket.IO events for semantic clarity (job:new for new jobs, job:accepted for removal)
- [Phase 04-01]: Broadcast to personal driver rooms (driver:{id}) instead of global rooms for targeted notifications
- [Phase 04-01]: All push notifications wrapped in try/except to ensure non-blocking operation
- [Phase 04-01]: Dual-channel notification system (APNs push for app alerts + Socket.IO for real-time feed updates)
- [Phase 04-02]: NotificationCenter bridge pattern for Socket.IO events to SwiftUI views (cleaner than @Observable property watching)
- [Phase 04-02]: Dual-channel notification: Socket.IO property (newJobAlert for LiveMapView) + NotificationCenter (feed updates)
- [Phase 04-02]: Animated list updates with withAnimation on real-time data changes (easeOut for removal, spring for addition)
- [Phase 04-03]: Push notification fallback handling - check categoryIdentifier first, then map userInfo["type"] to category
- [Phase 04-03]: "Driver Assigned" badge for "accepted" status (distinct from "assigned" for operator delegation)
- [Phase 04-03]: Foreground refresh pattern for booking list using NotificationCenter.default.publisher
- [Phase 04-04]: Human verification checkpoints for integration-heavy phases before phase completion
- [Phase 04-04]: End-to-end verification traces data flow across all 3 subsystems (backend, driver app, customer app)

**From Phase 5 (complete):**
- [Phase 05-01]: Auto-approve price decreases without customer interaction (better UX, no negative surprise)
- [Phase 05-01]: $50 flat trip fee on customer decline after driver arrives (compensates driver for wasted time)
- [Phase 05-01]: APNs category "VOLUME_ADJUSTMENT" for actionable notification with approve/decline buttons
- [Phase 05-01]: Socket.IO events to driver room only for volume workflow (customer gets push, driver gets socket)
- [Phase 05-01]: Graceful Stripe failure handling with try/except (log warning but don't fail endpoint in dev mode)
- [Phase 05-02]: Decimal keyboard with input filtering (digits and single decimal point, max 1 decimal place)
- [Phase 05-02]: NotificationCenter bridge pattern for Socket.IO volume events (consistent with Phase 4 job feed pattern)
- [Phase 05-02]: Overlay-based status UI for waiting/approved/declined states (full-screen feedback with blocked interaction)
- [Phase 05-03]: Approve/Decline actions use .foreground option to open app on tap for context
- [Phase 05-03]: Volume adjustment banner embedded inline with booking card for contextual relevance
- [Phase 05-03]: NotificationCenter bridge pattern for foreground volume adjustment push refresh (cleaner than property watching)
- [Phase 05-04]: End-to-end verification confirms all 5 VOL requirements fully implemented across backend, driver app, and customer app

**From Phase 6 (in progress):**
- [Phase 06-01]: kCLLocationAccuracyNearestTenMeters for battery optimization (not Best accuracy)
- [Phase 06-01]: 5-second throttle interval with 20m distance filter balances real-time tracking and battery life
- [Phase 06-01]: Location streaming lifecycle tied to job status (en_route starts, completed stops)
- [Phase 06-01]: Category field added to all push notifications for deep linking consistency
- [Phase 06-02]: ObservableObject for CustomerSocketManager (consistent with Phase 1 iOS 16 compatibility decision)
- [Phase 06-02]: NotificationCenter bridge pattern for Socket.IO events (consistent with Phase 4 pattern)
- [Phase 06-02]: Car icon annotation on MapKit for driver tracking (better UX than generic pin)
- [Phase 06-02]: Status-based color coding for job states (en_route=blue, arrived=orange, in_progress=red, completed=green)
- [Phase 06-02]: Socket.IO room management in view lifecycle (join on appear, leave on disappear)
- [Phase 06-03]: Track Driver button only shown for trackable statuses (en_route, arrived, started)
- [Phase 06-03]: Status badges show explicit labels before generic fallback
- [Phase 06-03]: Track Driver button only shown for trackable statuses (en_route, arrived, started)
- [Phase 06-03]: Status badges show explicit labels before generic fallback

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed 06-03: Tracking view integration and end-to-end verification
Resume file: None
