---
phase: 05-volume-adjustment
plan: 01
subsystem: backend
tags: [volume-adjustment, pricing, stripe, push-notifications, socket-io]
dependency_graph:
  requires:
    - Phase 3 Stripe PaymentIntent creation
    - Phase 4 push notification infrastructure
    - Phase 4 Socket.IO personal rooms
    - Phase 2 pricing calculation (calculate_estimate)
  provides:
    - Volume adjustment proposal endpoint (driver)
    - Volume adjustment approval/decline endpoints (customer)
    - APNs category support for actionable notifications
    - Auto-approval for price decreases
    - Trip fee on customer decline
  affects:
    - Job model (volume_adjustment_proposed, adjusted_volume, adjusted_price)
    - Payment amounts and Stripe PaymentIntent
    - Job status (cancelled on decline)
tech_stack:
  added:
    - APNs category field in push payload
  patterns:
    - Lazy imports for circular dependency avoidance (booking.calculate_estimate, socketio, stripe)
    - Auto-approve pattern for customer-friendly price decreases
    - Graceful Stripe failure handling with try/except
    - Dual notification: push (actionable) + Socket.IO (real-time)
    - Trip fee compensation model ($50 flat fee)
key_files:
  created: []
  modified:
    - backend/models.py (volume adjustment fields)
    - backend/push_notifications.py (category parameter)
    - backend/notifications.py (category parameter passthrough)
    - backend/routes/drivers.py (POST /api/drivers/jobs/<id>/volume)
    - backend/routes/jobs.py (POST /api/jobs/<id>/volume/approve, /volume/decline)
decisions:
  - Auto-approve price decreases without customer interaction (better UX, no negative surprise)
  - $50 flat trip fee on customer decline (compensates driver for wasted time)
  - Volume tier mapping reused from Phase 2 (consistent pricing logic)
  - APNs category "VOLUME_ADJUSTMENT" for actionable notification with approve/decline buttons
  - Socket.IO events to driver room only (customer gets push notification, not socket event)
  - Graceful Stripe failure handling (log warning but don't fail endpoint in dev mode)
metrics:
  duration_minutes: 3.15
  tasks_completed: 2
  commits: 2
  files_modified: 5
  completed_date: 2026-02-14
---

# Phase 5 Plan 1: Volume Adjustment Workflow Summary

Backend volume adjustment workflow complete: driver proposes new volume/price, customer approves via actionable push notification, Stripe PaymentIntent updates automatically.

## One-liner

Volume adjustment workflow with auto-approval for price decreases, customer push approval for increases, and $50 trip fee on decline using APNs category actions and Stripe PaymentIntent updates.

## What Was Built

### Job Model Extensions
- `volume_adjustment_proposed` (Boolean) — Flags pending customer decision
- `adjusted_volume` (Float) — Driver's measured actual volume
- `adjusted_price` (Float) — Recalculated price from driver's volume
- All three fields exposed in `Job.to_dict()` for API responses

### APNs Category Support
- Added `category` parameter to push notification stack:
  - `push_notifications.send_push_to_token()` accepts category
  - `push_notifications.send_push_notification()` passes category through
  - `notifications.send_push_notification()` wrapper accepts and forwards category
- Category flows to APNs `aps.category` field for iOS actionable notifications

### Driver Endpoint: Volume Proposal
**POST /api/drivers/jobs/<id>/volume**
- Requires `actual_volume` (float) in request body
- Validates job status == "arrived" and requesting user is assigned driver
- Recalculates price using Phase 2 volume tier mapping:
  - ≤4 cu yd → quarter (2 items)
  - ≤8 cu yd → half (5 items)
  - ≤12 cu yd → threeQuarter (10 items)
  - >12 cu yd → full (16 items)
- Calls `calculate_estimate()` with mapped items to get new price

**Auto-approve path (price decreased or equal):**
- Updates `job.total_price` and `job.volume_estimate` immediately
- Updates Stripe PaymentIntent to new amount
- Updates Payment record (amount, commission, driver_payout_amount)
- Emits `volume:approved` Socket.IO event to driver room
- Returns `{"success": true, "auto_approved": true, "new_price": <amount>}`

**Approval required path (price increased):**
- Sets `volume_adjustment_proposed = true`
- Sets `adjusted_volume` and `adjusted_price`
- Sends push to customer with `category="VOLUME_ADJUSTMENT"`:
  - Title: "Price Adjustment Required"
  - Body: "Volume increased. New price: $X.XX (was $Y.YY)"
  - Data: job_id, new_price, original_price, type
- Emits `volume:proposed` Socket.IO event to driver room
- Returns `{"success": true, "new_price": <amount>, "original_price": <amount>}`

### Customer Endpoints: Approve/Decline

**POST /api/jobs/<id>/volume/approve**
- Validates job.customer_id == authenticated user
- Returns 409 if `volume_adjustment_proposed == false` (idempotent)
- Updates Stripe PaymentIntent to `adjusted_price`
- Updates Payment record (amount, commission, driver_payout_amount)
- Updates job: `total_price = adjusted_price`, `volume_estimate = adjusted_volume`, `volume_adjustment_proposed = false`
- Emits `volume:approved` Socket.IO event to driver room
- Returns `{"success": true}`

**POST /api/jobs/<id>/volume/decline**
- Validates job.customer_id == authenticated user
- Returns 409 if `volume_adjustment_proposed == false` (idempotent)
- Updates Stripe PaymentIntent to $50 trip fee
- Updates Payment record (amount = 50, commission = 10, driver_payout_amount = 40)
- Updates job: `status = "cancelled"`, `cancelled_at = now()`, `cancellation_fee = 50`, `volume_adjustment_proposed = false`
- Emits `volume:declined` Socket.IO event to driver room with trip_fee
- Returns `{"success": true, "trip_fee": 50.0}`

### Error Handling
- All Stripe API calls wrapped in try/except with warning logs (non-blocking in dev mode)
- Socket.IO emit failures logged as warnings (non-blocking)
- Push notification failures logged as warnings (non-blocking)

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **Auto-approve price decreases**: No customer interaction needed when price goes down (better UX, eliminates negative surprise)
2. **$50 flat trip fee**: Compensates driver for wasted time after arriving on-site when customer declines higher price
3. **APNs category for actionable notifications**: "VOLUME_ADJUSTMENT" category enables iOS to show approve/decline buttons directly in notification
4. **Socket.IO to driver only**: Customer receives push notification (actionable), driver receives Socket.IO events (real-time feed updates)
5. **Graceful Stripe failure**: Log warnings but don't fail endpoint if Stripe API is unavailable (supports local dev without Stripe)
6. **Reuse Phase 2 volume tier mapping**: Consistent pricing logic across booking and volume adjustment flows

## Testing Notes

### Unit Test Verification (Task 1)
```bash
# Verified Job model fields
python3 -c "from models import Job; j = Job(); print(j.volume_adjustment_proposed, j.adjusted_volume, j.adjusted_price)"
# Output: None None None (correct - nullable fields with defaults)

# Verified category parameter exists
python3 -c "from push_notifications import send_push_notification; import inspect; sig = inspect.signature(send_push_notification); print('category' in sig.parameters)"
# Output: True
```

### Import Verification (Task 2)
```bash
# Verified drivers.py imports successfully
python3 -c "from routes.drivers import drivers_bp; print('drivers_bp imported successfully')"

# Verified jobs.py imports successfully
python3 -c "from routes.jobs import jobs_bp; print('jobs_bp imported successfully')"
```

### Manual Testing Checklist (for next session)
- [ ] Driver proposes volume increase (price goes up) → customer receives push with category
- [ ] Customer approves via notification action → job.total_price updated, Stripe PaymentIntent updated
- [ ] Customer declines via notification action → job.status = "cancelled", $50 trip fee charged
- [ ] Driver proposes volume decrease (price goes down) → auto-approved, no customer push sent
- [ ] Socket.IO events received in driver app (volume:proposed, volume:approved, volume:declined)
- [ ] Push notification shows approve/decline buttons (requires iOS app with UNNotificationCategory registration)

## Integration Points

### Dependencies
- **Phase 2**: `calculate_estimate()` from routes/booking.py (pricing calculation)
- **Phase 3**: Stripe PaymentIntent (amount updates on approve/decline)
- **Phase 3**: Payment model (commission and driver_payout_amount recalculation)
- **Phase 4**: APNs push infrastructure (notifications.send_push_notification)
- **Phase 4**: Socket.IO personal rooms (driver:{id} for targeted events)

### Enables
- **Phase 5 Plan 2**: iOS driver app UI for volume input and proposal
- **Phase 5 Plan 3**: iOS customer app actionable notification handler (UNNotificationCategory)
- **Phase 5 Plan 4**: End-to-end volume adjustment verification

## Implementation Notes

### Lazy Imports Pattern (continued from Phase 4)
```python
# Inside function body to avoid circular dependency
from routes.booking import calculate_estimate
from notifications import send_push_notification
from socket_events import socketio
import stripe
```

### Volume Tier Mapping (from Phase 2)
| Actual Volume | Tier | Item Quantity |
|---------------|------|---------------|
| ≤4 cu yd | quarter | 2 |
| ≤8 cu yd | half | 5 |
| ≤12 cu yd | threeQuarter | 10 |
| >12 cu yd | full | 16 |

### APNs Category Payload Structure
```json
{
  "aps": {
    "alert": {
      "title": "Price Adjustment Required",
      "body": "Volume increased. New price: $X.XX (was $Y.YY)"
    },
    "category": "VOLUME_ADJUSTMENT",
    "sound": "default"
  },
  "job_id": "...",
  "new_price": "150.00",
  "original_price": "100.00",
  "type": "volume_adjustment"
}
```

### Socket.IO Events
| Event | Room | Payload | Trigger |
|-------|------|---------|---------|
| volume:proposed | driver:{id} | {job_id, new_price} | Driver proposes increase |
| volume:approved | driver:{id} | {job_id} | Customer approves or auto-approved |
| volume:declined | driver:{id} | {job_id, trip_fee} | Customer declines |

## Task Breakdown

### Task 1: Add volume adjustment fields to Job model and APNs category support
**Duration:** ~1.5 minutes
**Commit:** e84b0cb

**Changes:**
- Added 3 columns to Job model: `volume_adjustment_proposed`, `adjusted_volume`, `adjusted_price`
- Added fields to `Job.to_dict()` for API exposure
- Added `category` parameter to `push_notifications.send_push_to_token()`
- Added `category` to APNs aps_payload construction
- Added `category` parameter to `push_notifications.send_push_notification()`
- Passed `category` through to `send_push_to_token()` calls
- Added `category` parameter to `notifications.send_push_notification()` wrapper

**Verification:** Unit tests confirmed field defaults and parameter presence.

### Task 2: Create volume adjustment endpoints and Socket.IO events
**Duration:** ~1.65 minutes
**Commit:** d978b02

**Changes:**
- Added POST /api/drivers/jobs/<id>/volume endpoint (drivers.py line 499)
  - 128 lines of volume adjustment proposal logic
  - Auto-approve path for price decreases
  - Customer approval path for price increases
  - Stripe PaymentIntent updates
  - Socket.IO event emissions
  - Push notification with category
- Added POST /api/jobs/<id>/volume/approve endpoint (jobs.py line 624)
  - 51 lines of approval logic
  - Stripe PaymentIntent update to adjusted_price
  - Payment record updates
  - Socket.IO volume:approved event
- Added POST /api/jobs/<id>/volume/decline endpoint (jobs.py line 677)
  - 53 lines of decline logic
  - Stripe PaymentIntent update to trip fee
  - Job cancellation with cancellation_fee
  - Socket.IO volume:declined event

**Verification:** Import tests confirmed blueprints load successfully and functions exist.

## Performance

**Execution time:** 3.15 minutes (189 seconds)
**Tasks completed:** 2/2
**Commits:** 2
**Files modified:** 5

## Next Steps

1. **Phase 5 Plan 2**: iOS driver app volume input UI and proposal flow
2. **Phase 5 Plan 3**: iOS customer app actionable notification handlers
3. **Phase 5 Plan 4**: End-to-end verification with real devices

## Self-Check: PASSED

### Files Created
None - all modifications to existing files.

### Files Modified
- [✓] backend/models.py exists and contains volume_adjustment_proposed, adjusted_volume, adjusted_price
- [✓] backend/push_notifications.py exists and contains category parameter
- [✓] backend/notifications.py exists and contains category parameter
- [✓] backend/routes/drivers.py exists and contains propose_volume_adjustment
- [✓] backend/routes/jobs.py exists and contains approve_volume_adjustment and decline_volume_adjustment

### Commits Exist
- [✓] e84b0cb: feat(05-01): add volume adjustment fields and APNs category support
- [✓] d978b02: feat(05-01): add volume adjustment workflow endpoints

### Key Functions Exist
```bash
grep -n "def propose_volume_adjustment" backend/routes/drivers.py
# 499:def propose_volume_adjustment(user_id, job_id):

grep -n "def approve_volume_adjustment\|def decline_volume_adjustment" backend/routes/jobs.py
# 624:def approve_volume_adjustment(user_id, job_id):
# 677:def decline_volume_adjustment(user_id, job_id):
```

All verification checks passed.
