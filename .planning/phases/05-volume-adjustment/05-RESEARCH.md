# Phase 5: Volume Adjustment - Research

**Researched:** 2026-02-14
**Domain:** On-site pricing recalculation, interactive iOS notifications, payment intent updates
**Confidence:** HIGH

## Summary

Phase 5 implements on-site volume adjustment with customer approval, allowing drivers to recalculate pricing when actual junk volume differs from the customer's estimate. This protects both parties: customers approve price changes before work continues, and drivers receive a trip fee if the customer declines after arrival.

The implementation requires three core systems: (1) iOS actionable push notifications for approve/decline actions, (2) backend payment intent updates to adjust held funds, and (3) driver-side volume input UI with real-time price recalculation. The project already has the foundation in place: Stripe payment intents with escrow (Phase 3), APNs push infrastructure (Phase 4), Socket.IO real-time messaging (Phase 4), and job status flow logic (backend/routes/jobs.py).

**Primary recommendation:** Use iOS UNNotificationCategory with approve/decline actions for customer response, update Stripe PaymentIntent amounts via the API, and wire Socket.IO events for real-time price change notifications between driver and customer apps.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| UserNotifications | iOS 16+ | Interactive push notifications | Native iOS framework for actionable notifications with buttons |
| Stripe PaymentIntent API | Latest | Update payment amounts | Official Stripe API supports amount updates before capture |
| Socket.IO | 5.x (Python), 4.x (Swift) | Real-time price change sync | Already integrated in Phase 4 for job status updates |
| Flask-SocketIO | 5.3+ | Backend WebSocket server | Already configured in backend/socket_events.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| NumberFormatter | iOS 16+ | Decimal input validation | Format volume input (e.g., "2.5 cubic yards") |
| HapticManager | Custom | Tactile feedback | Already exists in both iOS apps for success/error states |
| NotificationCenter | iOS 16+ | In-app event broadcasting | Already used in Phase 4 for Socket.IO to SwiftUI bridging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Actionable notifications | Deep link to in-app approval screen | Worse UX: requires app open, 2+ extra taps. Actionable notifications allow instant approve/decline from lock screen. |
| Stripe PaymentIntent update | Create new PaymentIntent | Complicates refund logic, loses transaction history. Update preserves single payment record. |
| Socket.IO real-time sync | Polling API every N seconds | Higher server load, delayed updates. Socket.IO already configured and battle-tested from Phase 4. |

**Installation:**
```bash
# Backend: Already installed (Phase 4)
pip install flask-socketio python-socketio stripe

# iOS: Already installed (Phase 4)
# SocketIO.framework via Swift Package Manager
# UserNotifications is built-in
```

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── routes/
│   ├── driver.py         # Add POST /api/driver/jobs/<id>/volume endpoint
│   └── jobs.py           # Add approve/decline volume endpoints
├── socket_events.py      # Add volume:proposed, volume:approved, volume:declined events
├── notifications.py      # Add volume_adjustment notification type
└── models.py             # Add volume_adjustment_proposed, adjusted_price fields to Job

JunkOS-Driver/
├── Views/ActiveJob/
│   ├── VolumeAdjustmentView.swift       # NEW: Driver volume input + price preview
│   └── ActiveJobView.swift              # Add navigation to VolumeAdjustmentView
├── ViewModels/
│   └── VolumeAdjustmentViewModel.swift  # NEW: Volume input, price calculation, API call
└── Managers/
    └── NotificationManager.swift        # Already exists, no changes needed

JunkOS-Clean/
├── Managers/
│   └── NotificationManager.swift        # Add volume adjustment category + actions
└── ViewModels/
    └── BookingDetailViewModel.swift     # Add volume approval/decline handling
```

### Pattern 1: Actionable Push Notifications
**What:** iOS UNNotificationCategory defines custom actions (buttons) displayed with push notifications. User taps trigger app delegate callbacks without opening the app.

**When to use:** Customer needs to approve/decline a price change instantly, ideally from lock screen or notification banner.

**Example:**
```swift
// Source: https://developer.apple.com/documentation/usernotifications/declaring-your-actionable-notification-types
import UserNotifications

// NotificationManager.swift init method
func registerVolumeAdjustmentCategory() {
    let approveAction = UNNotificationAction(
        identifier: "APPROVE_VOLUME",
        title: "Approve New Price",
        options: [.foreground] // Opens app
    )

    let declineAction = UNNotificationAction(
        identifier: "DECLINE_VOLUME",
        title: "Decline & Cancel",
        options: [.destructive]
    )

    let category = UNNotificationCategory(
        identifier: "VOLUME_ADJUSTMENT",
        actions: [approveAction, declineAction],
        intentIdentifiers: [],
        options: [.customDismissAction]
    )

    UNUserNotificationCenter.current().setNotificationCategories([category])
}

// Handling response (already have delegate pattern from Phase 4)
func userNotificationCenter(
    _ center: UNUserNotificationCenter,
    didReceive response: UNNotificationResponse,
    withCompletionHandler completionHandler: @escaping () -> Void
) {
    let jobId = response.notification.request.content.userInfo["job_id"] as? String

    switch response.actionIdentifier {
    case "APPROVE_VOLUME":
        Task { await approveVolumeAdjustment(jobId: jobId) }
    case "DECLINE_VOLUME":
        Task { await declineVolumeAdjustment(jobId: jobId) }
    default:
        break
    }
    completionHandler()
}
```

### Pattern 2: Stripe PaymentIntent Amount Update
**What:** Stripe allows updating PaymentIntent amount before capture (payment confirmation). Umuve holds payment in escrow during job (Phase 3), so we can adjust the amount on-site.

**When to use:** Customer approves higher price due to increased volume. Update the existing PaymentIntent rather than creating a new one.

**Example:**
```python
# Source: https://docs.stripe.com/api/payment_intents/update
import stripe

# backend/routes/jobs.py or routes/driver.py
@driver_bp.route("/jobs/<job_id>/volume", methods=["POST"])
@require_auth
def propose_volume_adjustment(user_id, job_id):
    """Driver proposes new volume and adjusted price."""
    data = request.get_json()
    actual_volume = data.get("actual_volume")  # cubic yards

    # Recalculate price using existing calculate_estimate() from routes/booking.py
    from routes.booking import calculate_estimate
    items = [{"category": "general", "quantity": int(actual_volume)}]
    estimate = calculate_estimate(items, scheduled_date=None, lat=None, lng=None)
    new_price = estimate["grand_total"]

    # Update job record
    job = db.session.get(Job, job_id)
    job.volume_adjustment_proposed = True
    job.adjusted_volume = actual_volume
    job.adjusted_price = new_price
    db.session.commit()

    # Send push notification to customer with VOLUME_ADJUSTMENT category
    send_push_notification(
        user_id=job.customer_id,
        title="Price Adjustment Required",
        body=f"Volume increased to {actual_volume} cu yd. New price: ${new_price:.2f}",
        data={"job_id": job_id, "new_price": new_price},
        category="VOLUME_ADJUSTMENT"  # Triggers approve/decline buttons
    )

    # Notify driver via Socket.IO that proposal was sent
    socketio.emit("volume:proposed", {"job_id": job_id, "new_price": new_price}, room=f"driver:{contractor.id}")

    return jsonify({"success": True, "new_price": new_price}), 200

@jobs_bp.route("/<job_id>/volume/approve", methods=["POST"])
@require_auth
def approve_volume_adjustment(user_id, job_id):
    """Customer approves new price."""
    job = db.session.get(Job, job_id)
    if job.customer_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Update Stripe PaymentIntent amount
    payment = job.payment
    if payment and payment.stripe_payment_intent_id:
        new_amount_cents = int(job.adjusted_price * 100)
        stripe.PaymentIntent.modify(
            payment.stripe_payment_intent_id,
            amount=new_amount_cents
        )
        payment.amount = job.adjusted_price

    # Update job with new price
    job.total_price = job.adjusted_price
    job.volume_estimate = job.adjusted_volume
    job.volume_adjustment_proposed = False
    db.session.commit()

    # Notify driver via Socket.IO
    socketio.emit("volume:approved", {"job_id": job_id}, room=f"driver:{job.driver_id}")

    return jsonify({"success": True}), 200

@jobs_bp.route("/<job_id>/volume/decline", methods=["POST"])
@require_auth
def decline_volume_adjustment(user_id, job_id):
    """Customer declines new price, job is cancelled with trip fee."""
    job = db.session.get(Job, job_id)
    if job.customer_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    TRIP_FEE = 50.0  # Fixed trip fee for driver arrival

    # Update Stripe PaymentIntent to trip fee only
    payment = job.payment
    if payment and payment.stripe_payment_intent_id:
        stripe.PaymentIntent.modify(
            payment.stripe_payment_intent_id,
            amount=int(TRIP_FEE * 100)
        )
        payment.amount = TRIP_FEE

    # Cancel job with trip fee
    job.status = "cancelled"
    job.cancelled_at = utcnow()
    job.cancellation_fee = TRIP_FEE
    job.volume_adjustment_proposed = False
    db.session.commit()

    # Notify driver via Socket.IO
    socketio.emit("volume:declined", {"job_id": job_id, "trip_fee": TRIP_FEE}, room=f"driver:{job.driver_id}")

    return jsonify({"success": True, "trip_fee": TRIP_FEE}), 200
```

### Pattern 3: Real-Time Price Sync via Socket.IO
**What:** Use Socket.IO personal rooms (driver:{id}, job:{id}) to push volume adjustment status updates in real-time. Driver sees "Waiting for customer approval" spinner, customer sees notification, approval triggers immediate driver-side update.

**When to use:** Driver needs instant feedback when customer approves/declines, avoiding manual refresh or polling.

**Example:**
```swift
// Source: Phase 04-02 pattern (already implemented)
// JunkOS-Driver/ViewModels/VolumeAdjustmentViewModel.swift

import Foundation
import Combine

@Observable
final class VolumeAdjustmentViewModel {
    var actualVolume: String = ""
    var calculatedPrice: Double = 0.0
    var isWaitingForApproval = false
    var wasApproved: Bool? = nil

    private var cancellables = Set<AnyCancellable>()

    init() {
        // Listen for Socket.IO events via NotificationCenter bridge
        NotificationCenter.default.publisher(for: NSNotification.Name("socket:volume:approved"))
            .sink { [weak self] _ in
                self?.wasApproved = true
                self?.isWaitingForApproval = false
                HapticManager.shared.success()
            }
            .store(in: &cancellables)

        NotificationCenter.default.publisher(for: NSNotification.Name("socket:volume:declined"))
            .sink { [weak self] _ in
                self?.wasApproved = false
                self?.isWaitingForApproval = false
                HapticManager.shared.error()
            }
            .store(in: &cancellables)
    }

    func proposeAdjustment(jobId: String) async {
        isWaitingForApproval = true
        do {
            let response = try await DriverAPIClient.shared.proposeVolumeAdjustment(
                jobId: jobId,
                actualVolume: Double(actualVolume) ?? 0.0
            )
            calculatedPrice = response.newPrice
        } catch {
            isWaitingForApproval = false
            // Handle error
        }
    }
}
```

### Pattern 4: Decimal Input Validation
**What:** SwiftUI TextField with NumberFormatter to accept decimal volume input (e.g., "2.5" cubic yards). Prevent invalid characters, limit decimal places, and format for display.

**When to use:** Driver enters actual volume measurement that requires fractional precision.

**Example:**
```swift
// Source: https://www.hackingwithswift.com/quick-start/swiftui/how-to-format-a-textfield-for-numbers
import SwiftUI

struct VolumeInputField: View {
    @Binding var volume: String

    var body: some View {
        TextField("Volume (cu yd)", text: $volume)
            .keyboardType(.decimalPad)
            .onChange(of: volume) { oldValue, newValue in
                // Allow only digits and single decimal point
                let filtered = newValue.filter { "0123456789.".contains($0) }
                let components = filtered.components(separatedBy: ".")
                if components.count > 2 {
                    // Multiple decimal points: keep only first
                    volume = components[0] + "." + components[1...].joined()
                } else if components.count == 2 && components[1].count > 2 {
                    // Limit to 2 decimal places
                    volume = components[0] + "." + String(components[1].prefix(2))
                } else {
                    volume = filtered
                }
            }
    }
}
```

### Anti-Patterns to Avoid
- **Deep linking for approval instead of actionable notifications:** Forces customer to open app, navigate to job detail, and tap button. Actionable notifications allow instant approve/decline from lock screen with 1 tap.
- **Creating new PaymentIntent for adjusted price:** Breaks escrow flow and complicates refund logic. Always update existing PaymentIntent amount.
- **Storing adjusted price in separate table:** Job model already has fields for cancellation_fee and volume_estimate. Add adjusted_price and adjusted_volume columns to jobs table, not a separate volume_adjustments table.
- **Silently updating price without customer approval:** Violates user trust and payment regulations. Always require explicit approval via push notification or in-app action.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interactive push notifications | Custom WebSocket message with confirm/cancel logic | iOS UNNotificationCategory + UNNotificationAction | System-level notification actions are deeply integrated with iOS UI, work from lock screen, respect notification settings, and handle edge cases (app backgrounded, notification dismissed, etc.) |
| Payment amount updates | Cancel + refund + create new PaymentIntent | Stripe PaymentIntent.modify(amount=...) | Official Stripe API maintains single transaction record, simplifies accounting, preserves payment method, and avoids duplicate charges |
| Decimal number input validation | Regex parsing of text input | NumberFormatter with ParseableFormatStyle | Handles locale-specific decimal separators (comma vs period), grouping separators, edge cases like multiple decimal points, and provides native formatting |
| Trip fee calculation | Custom formula based on distance/time | Fixed trip fee constant (e.g., $50) | Simpler to implement, easier to communicate to users, avoids disputes over "fair" calculation. Can be upgraded to dynamic formula later if needed. |

**Key insight:** Volume adjustment workflow touches payment processing (regulated), push notifications (OS-level), and real-time sync (stateful). Each domain has battle-tested solutions that handle edge cases (network failures, app crashes, notification permissions denied, payment failures) better than custom implementations.

## Common Pitfalls

### Pitfall 1: Notification Permission Denial
**What goes wrong:** Customer denies push notification permission, never receives volume adjustment alert, driver waits indefinitely.

**Why it happens:** iOS requires explicit user permission for push notifications. Customer may decline during onboarding or disable in Settings later.

**How to avoid:** Add in-app fallback: if push notification fails to send (check APNs device token exists), emit Socket.IO event to customer's active session. If customer app is open, show in-app alert. If app is closed, driver should see "Customer hasn't responded" after timeout (e.g., 5 minutes) and get option to call customer or cancel job.

**Warning signs:** APNs device token is nil or empty, push notification send returns error, customer doesn't respond within 2-3 minutes.

### Pitfall 2: Race Condition on Approve/Decline
**What goes wrong:** Customer taps "Approve" and "Decline" in quick succession (notification stacking, accidental double-tap), or driver cancels job while customer is approving.

**Why it happens:** Network latency means API calls arrive out-of-order. Notification actions don't auto-dismiss on first tap.

**How to avoid:** Add idempotency check: store volume_adjustment_proposed boolean on Job model, set to true when driver proposes, set to false on approve/decline. Approve/decline endpoints return 409 Conflict if volume_adjustment_proposed is false. Also lock Job status transitions: only allow approve/decline if job.status == "arrived" and job.volume_adjustment_proposed == true.

**Warning signs:** Job status changes to cancelled after customer approved, multiple API calls with same job_id in logs within 1-2 seconds.

### Pitfall 3: Stripe PaymentIntent Already Captured
**What goes wrong:** Attempt to update PaymentIntent amount after it's been captured (payment confirmed), Stripe API returns error.

**Why it happens:** Phase 3 payment flow uses Stripe's automatic capture (payment confirmed immediately after card authorization). Volume adjustment requires manual capture (hold funds until job completes).

**How to avoid:** Phase 5 requires changing Phase 3 payment flow to manual capture: when creating PaymentIntent, set `capture_method="manual"`. After job completion (status="completed"), call `stripe.PaymentIntent.capture()`. This allows amount updates during job (arrived → started → completed).

**Warning signs:** Stripe API error "cannot modify amount on payment_intent with status succeeded", payment captured before job status changes to "completed".

### Pitfall 4: Customer Approval Timeout
**What goes wrong:** Customer doesn't respond to volume adjustment notification within reasonable time (distracted, phone on silent, notification dismissed), driver waits indefinitely at job site.

**Why it happens:** No timeout mechanism for customer response.

**How to avoid:** Add 5-minute timeout: backend sets expiration timestamp when volume adjustment is proposed. If customer hasn't responded within 5 minutes, notify driver "Customer hasn't responded. You can call them or cancel the job with trip fee." Driver gets options: (1) Call customer (triggers phone:// deep link), (2) Wait longer (extends timeout), (3) Cancel with trip fee.

**Warning signs:** Driver socket connected but no approve/decline event within 5+ minutes, customer device token exists but no API call from customer app.

### Pitfall 5: Price Decrease Rejected by Customer
**What goes wrong:** Driver measures less volume than estimated, proposes lower price, customer declines (expecting original price), driver confused why customer declined savings.

**Why it happens:** Workflow assumes price always increases. Lower price decline doesn't make logical sense but is technically possible.

**How to avoid:** Add price direction check: if new_price < original_price, auto-approve without customer notification. Customer only sees volume adjustment notification if new_price > original_price. Log price decreases for transparency but proceed with lower price automatically.

**Warning signs:** Customer declines price adjustment where new_price < total_price, driver complaints about "customer rejecting lower price".

## Code Examples

Verified patterns from official sources:

### Registering Notification Categories
```swift
// Source: https://developer.apple.com/documentation/usernotifications/declaring-your-actionable-notification-types
import UserNotifications

func setupNotificationCategories() {
    let approveAction = UNNotificationAction(
        identifier: "APPROVE_VOLUME",
        title: "Approve New Price",
        options: [.foreground]
    )

    let declineAction = UNNotificationAction(
        identifier: "DECLINE_VOLUME",
        title: "Decline & Cancel",
        options: [.destructive]
    )

    let volumeCategory = UNNotificationCategory(
        identifier: "VOLUME_ADJUSTMENT",
        actions: [approveAction, declineAction],
        intentIdentifiers: [],
        options: [.customDismissAction]
    )

    // Register alongside existing categories
    UNUserNotificationCenter.current().setNotificationCategories([
        volumeCategory,
        // ... other categories from Phase 4
    ])
}
```

### Sending APNs Push with Category
```python
# Source: backend/push_notifications.py (already implemented in Phase 4)
# Add category parameter to send_push_notification()

def send_push_notification(user_id, title, body, data=None, category=None):
    """Send APNs push notification to user's registered devices."""
    device_tokens = DeviceToken.query.filter_by(user_id=user_id).all()

    for token in device_tokens:
        payload = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "badge": 1
            }
        }

        if category:
            payload["aps"]["category"] = category  # Triggers UNNotificationCategory

        if data:
            payload.update(data)

        # Send via httpx (already configured in push_notifications.py)
        _send_apns_request(token.device_token, payload)
```

### Updating Stripe PaymentIntent Amount
```python
# Source: https://docs.stripe.com/api/payment_intents/update
import stripe

def update_payment_amount(payment_intent_id, new_amount_cents):
    """Update PaymentIntent amount before capture."""
    try:
        intent = stripe.PaymentIntent.modify(
            payment_intent_id,
            amount=new_amount_cents,  # Must be integer (cents)
            metadata={"adjusted": "true", "reason": "volume_increase"}
        )
        return intent
    except stripe.error.InvalidRequestError as e:
        # Handle error: PaymentIntent already captured or cancelled
        logger.error(f"Cannot update PaymentIntent: {e}")
        return None
```

### Socket.IO Event Emission to Personal Rooms
```python
# Source: backend/socket_events.py (already implemented in Phase 4)
from flask_socketio import emit

def notify_driver_volume_response(driver_id, job_id, approved):
    """Emit volume approval/decline to driver's personal room."""
    event = "volume:approved" if approved else "volume:declined"
    socketio.emit(event, {"job_id": job_id}, room=f"driver:{driver_id}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual price negotiation via phone call | Real-time in-app volume adjustment with push notification approval | 2023-2024 (Uber/Lyft surge pricing model) | Faster resolution, transparent pricing, digital paper trail prevents disputes |
| Create new payment for adjusted amount | Update existing PaymentIntent amount | Stripe API v2 (2020+) | Single transaction record, simpler refunds, better accounting |
| Polling API for customer response | Socket.IO real-time events | WebSocket adoption 2015+, Socket.IO 4.x (2021) | Instant updates, lower server load, better battery life |
| Email/SMS approval links | Actionable push notifications | iOS 10+ UNNotificationCategory (2016) | Instant approval from lock screen, 1-tap vs 3-tap flow, native iOS UI |

**Deprecated/outdated:**
- **Polling for customer response:** WebSockets/Socket.IO are standard now, polling wastes bandwidth and battery
- **Separate payment for adjustment:** Stripe PaymentIntent.modify() has been available since 2018, no reason to create new payment
- **SMS approval links:** Push notifications are faster, free, and don't require cellular signal (work on WiFi)

## Open Questions

1. **Trip fee amount**
   - What we know: Backend has cancellation_fee field on Job model, existing cancellation logic charges $25-50 based on timing (routes/jobs.py lines 218-220)
   - What's unclear: Should trip fee for volume decline match cancellation fee structure or be fixed amount?
   - Recommendation: Use fixed $50 trip fee for Phase 5 MVP. Simpler to implement and communicate. Can adjust based on user feedback in later phase.

2. **Stripe capture timing**
   - What we know: Phase 3 payment flow uses automatic capture (payment confirmed immediately)
   - What's unclear: Does Phase 3 need refactoring to manual capture before implementing Phase 5?
   - Recommendation: YES - Phase 5 requires manual capture. Add this to Phase 5 Plan 1 (backend changes). Update backend/routes/payments.py to set capture_method="manual", add capture call on job completion.

3. **Volume adjustment frequency limit**
   - What we know: Driver can propose volume adjustment when status="arrived"
   - What's unclear: Can driver propose multiple times if customer declines first attempt with lower volume?
   - Recommendation: Allow 1 adjustment per job. If customer declines, only options are cancel with trip fee or proceed at original price. Prevents endless negotiation loop.

4. **Customer app notification permission fallback**
   - What we know: Customer may deny push notification permission
   - What's unclear: What's the UX flow when customer app is open but push permission denied?
   - Recommendation: Add Socket.IO listener in customer app (customer:{user_id} room). If push fails, emit socket event. Show in-app alert modal with approve/decline buttons. This requires customer app to join personal room on login (similar to driver app in Phase 4).

## Sources

### Primary (HIGH confidence)
- [UNNotificationCategory | Apple Developer Documentation](https://developer.apple.com/documentation/usernotifications/unnotificationcategory)
- [Declaring your actionable notification types | Apple Developer Documentation](https://developer.apple.com/documentation/usernotifications/declaring-your-actionable-notification-types)
- [UNNotificationAction | Apple Developer Documentation](https://developer.apple.com/documentation/usernotifications/unnotificationaction)
- [Update a PaymentIntent | Stripe API Reference](https://docs.stripe.com/api/payment_intents/update)
- [The Payment Intents API | Stripe Documentation](https://docs.stripe.com/payments/payment-intents)
- [Cancel a PaymentIntent | Stripe API Reference](https://docs.stripe.com/api/payment_intents/cancel)

### Secondary (MEDIUM confidence)
- [How to add custom actions to iOS push and local notifications in SwiftUI](https://tanaschita.com/ios-notifications-custom-actions/)
- [iOS Notifications in 2026: Complete Developer Guide | Medium](https://medium.com/@thakurneeshu280/the-complete-guide-to-ios-notifications-from-basics-to-advanced-2026-edition-48cdcba8c18c)
- [How to format a TextField for numbers - SwiftUI by Example](https://www.hackingwithswift.com/quick-start/swiftui/how-to-format-a-textfield-for-numbers)
- [Advanced SwiftUI TextField - Formatting and Validation](https://fatbobman.com/en/posts/textfield-1/)
- [Checklist of 21 Services Marketplace Features | Rigby Blog](https://www.rigbyjs.com/blog/services-marketplace-features)

### Tertiary (LOW confidence)
- [Actionable Notifications With the User Notifications Framework](https://cocoacasts.com/actionable-notifications-with-the-user-notifications-framework)
- [Swift/iOS: Custom Actionable Push Notification | Level Up Coding](https://levelup.gitconnected.com/swift-ios-custom-actionable-push-notification-01e3e294265e)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - iOS UNNotificationCategory and Stripe PaymentIntent API are official, well-documented, and already partially integrated
- Architecture: HIGH - Patterns follow Phase 4 Socket.IO implementation (already working) and Phase 3 Stripe integration (already working)
- Pitfalls: MEDIUM - Based on common marketplace patterns and official documentation, but some edge cases may emerge during implementation

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days for stable APIs)
