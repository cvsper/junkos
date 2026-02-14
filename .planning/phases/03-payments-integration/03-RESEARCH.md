# Phase 3: Payments Integration - Research

**Researched:** 2026-02-14
**Domain:** Stripe payments, iOS Payment Sheet, Stripe Connect, marketplace payouts
**Confidence:** HIGH

## Summary

Phase 3 integrates Stripe payment processing into both customer and driver apps. The customer app will present Stripe's native Payment Sheet (with Apple Pay + card entry) after the Review step, while the driver app will implement Stripe Connect onboarding and display earnings dashboards. The backend already has foundational payment routes but requires webhook handling enhancements and escrow mechanics.

**Key findings:**
- Stripe iOS SDK 25.6.0 supports iOS 13+ and installs via Swift Package Manager
- Payment Sheet provides native Apple Pay + card entry with zero custom UI required
- Stripe Connect hosted onboarding uses SFSafariViewController for web-based account setup
- Backend escrow functionality uses PaymentIntent (auto-capture by default) with manual payout control
- 20% platform commission split is already implemented in backend with `PLATFORM_COMMISSION = 0.20`

**Primary recommendation:** Use Stripe's pre-built Payment Sheet and hosted Connect onboarding to minimize custom implementation. Leverage existing backend payment routes (`/api/payments/create-intent-simple`, `/api/payments/confirm-simple`, `/api/payments/earnings`) with minor enhancements for webhook reliability and driver payout triggering.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Payment Flow UX:**
- Payment happens BEFORE job creation — no job exists without successful payment
- Fresh card entry each booking (no saved cards for MVP)
- Use Stripe's native Payment Sheet (Apple Pay + card entry) — no custom card form
- Payment sheet appears after the existing Review step as the final action before job creation

**Driver Earnings Experience:**
- Detailed breakdown: per-job earnings list with dates, amounts, and payout status, plus summary totals (today, this week, all-time)
- Show driver's 80% take only — do NOT show the full job price or commission deduction
- Full earnings history (all time) with date range filters: today, this week, this month, custom
- Each job shows payout status: Pending → Processing → Paid

**Stripe Connect Onboarding:**
- Use SFSafariViewController (in-app browser) for Stripe Connect onboarding flow
- Stripe Connect setup is REQUIRED as part of initial driver signup — prompted right after sign-in, before accessing the app
- Block driver from job feed entirely until Stripe Connect setup is complete — show a setup-required screen
- Settings shows payout status badge (Not set up / Pending verification / Active) with action button to complete or update setup

### Claude's Discretion

- Post-payment confirmation UI design (overlay vs screen — match existing patterns)
- Exact earnings dashboard layout and typography
- Error handling for payment failures (card declined, network issues)
- Stripe webhook handling architecture
- Escrow release timing and mechanics

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Stripe iOS SDK | 25.6.0+ | Payment Sheet, Apple Pay integration | Official Stripe SDK, actively maintained, supports iOS 13+ |
| Swift Package Manager | Built-in | SDK installation | Native Xcode integration, recommended by Stripe |
| SFSafariViewController | iOS SDK | Stripe Connect onboarding | Apple's secure web view for OAuth flows |
| URLSession | iOS SDK | Backend API calls (PaymentIntent, confirm) | Standard iOS networking for non-Stripe calls |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PassKit | iOS SDK | Apple Pay payment requests | Already used in existing PaymentService.swift |
| Foundation | iOS SDK | Date formatting, number formatting for earnings | Dashboard date range filters |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Payment Sheet | Custom card form | Payment Sheet includes Apple Pay, Link, PCI compliance, validation — custom form requires manual implementation and increases security risk |
| Hosted onboarding | Embedded components | Embedded components are iOS beta (`@_spi(PrivateBetaConnect)`), hosted onboarding is production-ready and stable |
| Auto-capture PaymentIntent | Manual capture | Auto-capture is simpler for MVP; manual capture adds 7-day hold complexity unnecessary for instant confirmation flow |

**Installation:**

Add via Xcode → File → Add Package Dependencies:
```
https://github.com/stripe/stripe-ios
```

Select latest version (25.6.0+), add `StripePaymentSheet` product to customer app target.

---

## Architecture Patterns

### Recommended Project Structure

```
JunkOS-Clean/JunkOS/
├── Services/
│   ├── PaymentService.swift       # Existing - add Payment Sheet methods
│   └── StripeConnectService.swift # NEW - account link generation, status checks
├── Views/
│   ├── Booking/
│   │   ├── BookingReviewView.swift      # Existing - add payment trigger
│   │   └── BookingPaymentView.swift     # NEW - Payment Sheet presentation wrapper
│   └── Payment/
│       └── PaymentSuccessOverlay.swift  # NEW - post-payment confirmation UI
├── ViewModels/
│   ├── BookingReviewViewModel.swift     # Existing - add payment orchestration
│   └── PaymentSheetViewModel.swift      # NEW - Payment Sheet state management

JunkOS-Driver/
├── Services/
│   └── StripeConnectService.swift # NEW - onboarding URL fetch, account status
├── Views/
│   ├── Onboarding/
│   │   └── StripeConnectOnboardingView.swift # NEW - mandatory setup screen
│   ├── Earnings/
│   │   └── EarningsView.swift    # Existing - enhance with API integration
│   └── Profile/
│       └── PayoutSettingsView.swift # Existing - add Connect status badge
├── ViewModels/
│   ├── StripeConnectViewModel.swift # NEW - onboarding flow state
│   └── EarningsViewModel.swift      # Existing - add API data fetching
```

### Pattern 1: Payment Sheet Presentation (Customer App)

**What:** Present Stripe Payment Sheet after user confirms booking details
**When to use:** Final step in booking wizard, after Review screen

**Example:**
```swift
import StripePaymentSheet

class PaymentSheetViewModel: ObservableObject {
    @Published var paymentSheet: PaymentSheet?
    @Published var isProcessing = false

    @MainActor
    func preparePaymentSheet(amount: Double, bookingId: String) async throws {
        // 1. Create PaymentIntent on backend
        let response = try await PaymentService.shared.createPaymentIntent(
            amountInDollars: amount,
            bookingId: bookingId
        )

        // 2. Configure Payment Sheet
        var configuration = PaymentSheet.Configuration()
        configuration.merchantDisplayName = "Umuve"
        configuration.applePay = .init(
            merchantId: "merchant.com.goumuve.app",
            merchantCountryCode: "US"
        )
        configuration.returnURL = "umuve://payment-return"

        // 3. Initialize Payment Sheet
        paymentSheet = PaymentSheet(
            paymentIntentClientSecret: response.clientSecret,
            configuration: configuration
        )
    }

    func handlePaymentResult(_ result: PaymentSheetResult) async {
        switch result {
        case .completed:
            // Confirm payment on backend, create job
            try? await confirmPaymentAndCreateJob()
        case .canceled:
            // User dismissed sheet
            isProcessing = false
        case .failed(let error):
            // Handle payment failure
            self.errorMessage = error.localizedDescription
        }
    }
}
```

### Pattern 2: Stripe Connect Onboarding (Driver App)

**What:** Redirect driver to Stripe-hosted onboarding in SFSafariViewController
**When to use:** Immediately after driver sign-in, before app access

**Example:**
```swift
import SafariServices

class StripeConnectViewModel: ObservableObject {
    @Published var onboardingURL: URL?
    @Published var isOnboardingComplete = false

    @MainActor
    func startOnboarding() async throws {
        // Fetch account link from backend
        let response = try await DriverAPIClient.shared.createConnectAccountLink()
        self.onboardingURL = URL(string: response.accountLinkURL)
    }

    func checkOnboardingStatus() async throws -> OnboardingStatus {
        let contractor = try await DriverAPIClient.shared.getCurrentContractor()

        // Check contractor.stripe_connect_id and charges_enabled
        if contractor.stripeConnectId != nil && contractor.chargesEnabled == true {
            return .active
        } else if contractor.stripeConnectId != nil {
            return .pendingVerification
        } else {
            return .notSetUp
        }
    }
}

// In view:
.sheet(item: $viewModel.onboardingURL) { url in
    SafariView(url: url)
        .onDisappear {
            Task {
                try? await viewModel.checkOnboardingStatus()
            }
        }
}

struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        return SFSafariViewController(url: url)
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}
```

### Pattern 3: Earnings Dashboard with Date Filters

**What:** Display per-job earnings list with period segmented control
**When to use:** Driver Earnings tab

**Example:**
```swift
class EarningsViewModel: ObservableObject {
    @Published var summary = EarningsSummary.empty
    @Published var entries: [EarningsEntry] = []
    @Published var selectedPeriod: Period = .today

    enum Period: String, CaseIterable {
        case today = "Today"
        case week = "This Week"
        case month = "This Month"
        case all = "All Time"
    }

    @MainActor
    func fetchEarnings() async throws {
        let response = try await DriverAPIClient.shared.getEarnings()

        // Server returns: total_earnings, earnings_7d, earnings_30d
        self.summary = EarningsSummary(
            todayEarnings: response.todayEarnings ?? 0,
            weekEarnings: response.earnings7d,
            monthEarnings: response.earnings30d,
            allTimeEarnings: response.totalEarnings
        )

        // Fetch detailed entries (requires new backend endpoint)
        self.entries = try await DriverAPIClient.shared.getEarningsHistory()
    }

    var displayedAmount: String {
        let amount: Double
        switch selectedPeriod {
        case .today: amount = summary.todayEarnings
        case .week: amount = summary.weekEarnings
        case .month: amount = summary.monthEarnings
        case .all: amount = summary.allTimeEarnings
        }
        return String(format: "$%.2f", amount)
    }
}
```

### Pattern 4: Backend Webhook Handler

**What:** Verify Stripe webhook signatures and process payment events
**When to use:** All Stripe webhooks (`payment_intent.succeeded`, `account.updated`)

**Example (Python):**
```python
import stripe
from flask import request

@webhook_bp.route("/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    try:
        # Verify signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    # Handle event
    if event["type"] == "payment_intent.succeeded":
        handle_payment_succeeded(event["data"]["object"])
    elif event["type"] == "account.updated":
        handle_account_updated(event["data"]["object"])

    return jsonify({"received": True}), 200

def handle_payment_succeeded(intent):
    # Mark payment as succeeded, transition job to "confirmed"
    payment = Payment.query.filter_by(
        stripe_payment_intent_id=intent["id"]
    ).first()

    if payment:
        payment.payment_status = "succeeded"
        job = db.session.get(Job, payment.job_id)
        if job and job.status == "pending":
            job.status = "confirmed"
        db.session.commit()
```

### Anti-Patterns to Avoid

- **Manual card form implementation:** Payment Sheet includes PCI compliance, Apple Pay, Link wallet, validation — never build custom card forms
- **Storing card details locally:** Stripe handles tokenization — never save raw card data in keychain or UserDefaults
- **Sync webhook processing:** Stripe expects 2xx response within 20 seconds — always return immediately and process async
- **Hardcoded Stripe keys:** Use environment variables and Config.swift for publishable/secret keys
- **Ignoring webhook signature verification:** Always verify `Stripe-Signature` header to prevent replay attacks
- **Blocking driver app without escape:** Provide "Skip for now" during testing, but enforce onboarding before job acceptance in production

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Payment UI | Custom card form with validation, Apple Pay integration | Stripe Payment Sheet | Handles PCI compliance, 40+ payment methods, Apple Pay, Link wallet, SCA compliance — building custom requires security audits and ongoing maintenance |
| Connect onboarding | Custom driver identity verification, bank account collection | Stripe hosted onboarding | Stripe handles KYC, identity verification, legal compliance across 40+ countries — custom solution requires legal review per jurisdiction |
| Webhook validation | Custom signature verification logic | `stripe.Webhook.construct_event()` | Stripe's library handles timestamp verification, replay attack prevention, and signature algorithm updates |
| Payout scheduling | Custom cron jobs to transfer funds | Stripe automatic payouts or manual triggers | Stripe handles ACH timing, failures, retries, and balance management — custom solution requires financial reconciliation logic |
| Apple Pay certificates | Manual CSR generation and Apple Developer portal management | Stripe-managed certificates | Stripe auto-renews Apple Pay certificates and handles key rotation |

**Key insight:** Stripe's pre-built solutions handle edge cases like expired authorizations (7-day card hold limits), failed bank transfers (retry logic), disputed charges (evidence collection), and international compliance (tax forms, identity verification) — all scenarios that cause production incidents when hand-rolled.

---

## Common Pitfalls

### Pitfall 1: Payment Sheet Dismissal Without Completion

**What goes wrong:** User taps outside Payment Sheet or hits back button, payment state becomes ambiguous
**Why it happens:** Payment Sheet allows cancellation by design, but apps often don't handle `.canceled` result
**How to avoid:**
- Check `PaymentSheetResult.canceled` case explicitly
- Reset UI state (stop loading spinner, re-enable "Pay" button)
- DO NOT create job on cancellation
- Consider analytics tracking for abandonment rate

**Warning signs:** Job created with no payment, duplicate PaymentIntents, "job already exists" errors

### Pitfall 2: Webhook Signature Verification Failure

**What goes wrong:** Backend returns 400 for legitimate Stripe webhooks, payments succeed but jobs stay in "pending"
**Why it happens:**
- Using JSON-parsed body instead of raw request body for verification
- Middleware (Express bodyParser) consuming request stream before webhook handler
- Wrong webhook secret (test mode vs live mode mismatch)

**How to avoid:**
- Capture `request.get_data(as_text=True)` before any JSON parsing
- Use webhook secret from specific endpoint in Stripe Dashboard (not API key)
- Test with Stripe CLI: `stripe listen --forward-to localhost:5000/api/webhooks/stripe`

**Warning signs:** "Invalid signature" errors in logs, webhooks failing in Stripe Dashboard

### Pitfall 3: Account Link Expiration

**What goes wrong:** Driver taps onboarding link, gets "This link has expired" error from Stripe
**Why it happens:**
- Account links expire after 5 minutes or first use
- Link previews (iOS Messages, Slack) auto-fetch links, consuming them
- Caching onboarding URL in app state

**How to avoid:**
- Generate fresh account link on each tap (never cache URL)
- Implement `refresh_url` that generates new link and redirects
- Show loading state while fetching link, then immediately present SFSafariViewController

**Warning signs:** "Account link expired" support tickets, drivers stuck on onboarding screen

### Pitfall 4: Escrow Release Without Job Completion

**What goes wrong:** Driver receives payout before job marked "complete", customer disputes charge
**Why it happens:**
- Automatic Stripe payouts enabled (default 2-day rolling)
- Backend triggers payout on job "accepted" instead of "completed"
- Webhook handlers process events out of order

**How to avoid:**
- Use manual payouts for driver accounts (set via `settings.payouts.schedule.interval = "manual"`)
- Only trigger `POST /api/payments/payout/{job_id}` when job.status == "completed"
- Add idempotency check: `if payment.payout_status == "paid": return`

**Warning signs:** Drivers paid for incomplete jobs, negative platform balance, Stripe Connect disputes

### Pitfall 5: Driver 80% Take Shown as Full Price

**What goes wrong:** Earnings dashboard shows `$150` when driver only receives `$120` (80%)
**Why it happens:** Backend returns `payment.amount` (full price) instead of `payment.driver_payout_amount`
**How to avoid:**
- Backend: `/api/payments/earnings` returns `driver_payout_amount` only
- iOS: Display `entry.amount` directly, never multiply by 0.8 client-side
- Add backend test: `assert response["earnings"]["total_earnings"] == sum(p.driver_payout_amount for p in payments)`

**Warning signs:** Drivers report earnings mismatch, payout less than dashboard shows

### Pitfall 6: No Retry Logic for Declined Cards

**What goes wrong:** Card declined due to temporary issue (network, bank timeout), user gives up
**Why it happens:** Payment Sheet handles retries internally, but backend doesn't inform user to try again
**How to avoid:**
- Check PaymentIntent status: if `requires_payment_method`, card was declined
- Show user-friendly error: "Card declined. Please try another card or payment method."
- DO NOT auto-retry same card (Stripe charges retry fee, may flag as fraud)
- Consider letting user update payment method within same PaymentIntent

**Warning signs:** High card decline rate (>5%), "payment failed" support tickets

### Pitfall 7: Apple Pay Not Showing in Payment Sheet

**What goes wrong:** Payment Sheet only shows card entry, Apple Pay missing despite configuration
**Why it happens:**
- Missing Apple Pay entitlement in Xcode
- Merchant ID mismatch between Stripe Dashboard and app config
- Device not enrolled in Wallet or region restrictions

**How to avoid:**
- Add `Apple Pay Payment Processing` capability in Xcode target
- Verify merchant ID: `merchant.com.goumuve.app` in both Stripe + Apple Developer
- Test on physical device (simulator may not show Apple Pay)
- Use `PKPaymentAuthorizationViewController.canMakePayments()` to debug

**Warning signs:** Apple Pay badge missing in Payment Sheet, "Merchant not configured" errors

---

## Code Examples

Verified patterns from official Stripe documentation and existing codebase:

### Customer Payment Flow (Complete Example)

```swift
// BookingReviewViewModel.swift
class BookingReviewViewModel: ObservableObject {
    @Published var isCreatingPayment = false
    @Published var paymentSheet: PaymentSheet?
    @Published var showSuccess = false
    @Published var errorMessage: String?

    private let paymentService = PaymentService.shared

    @MainActor
    func confirmBooking(bookingData: BookingData) async {
        guard let totalPrice = bookingData.estimatedPrice else { return }

        isCreatingPayment = true
        defer { isCreatingPayment = false }

        do {
            // 1. Create PaymentIntent on backend
            let intentResponse = try await paymentService.createPaymentIntent(
                amountInDollars: totalPrice,
                bookingId: nil, // No job yet
                customerEmail: nil
            )

            // 2. Configure Payment Sheet
            var config = PaymentSheet.Configuration()
            config.merchantDisplayName = "Umuve"
            config.applePay = .init(
                merchantId: "merchant.com.goumuve.app",
                merchantCountryCode: "US"
            )
            config.returnURL = "umuve://payment-return"
            config.allowsDelayedPaymentMethods = false // Instant payment only

            // 3. Present Payment Sheet
            paymentSheet = PaymentSheet(
                paymentIntentClientSecret: intentResponse.clientSecret,
                configuration: config
            )

        } catch {
            errorMessage = "Failed to prepare payment: \(error.localizedDescription)"
        }
    }

    @MainActor
    func handlePaymentResult(_ result: PaymentSheetResult) async {
        switch result {
        case .completed:
            // Payment succeeded, now create job
            await createJobWithPayment()

        case .canceled:
            // User dismissed sheet
            print("Payment cancelled by user")

        case .failed(let error):
            errorMessage = "Payment failed: \(error.localizedDescription)"
        }
    }

    @MainActor
    private func createJobWithPayment() async {
        // Upload photos first, then create job (existing Phase 2 logic)
        // ...existing implementation from BookingReviewViewModel

        showSuccess = true
    }
}

// BookingReviewView.swift
struct BookingReviewView: View {
    @StateObject private var viewModel = BookingReviewViewModel()

    var body: some View {
        VStack {
            // ...existing review UI

            Button("Confirm & Pay") {
                Task {
                    await viewModel.confirmBooking(bookingData: bookingData)
                }
            }
            .disabled(viewModel.isCreatingPayment)
        }
        .paymentSheet(
            isPresented: Binding(
                get: { viewModel.paymentSheet != nil },
                set: { if !$0 { viewModel.paymentSheet = nil } }
            ),
            paymentSheet: viewModel.paymentSheet!,
            onCompletion: { result in
                Task {
                    await viewModel.handlePaymentResult(result)
                }
            }
        )
    }
}
```

### Driver Stripe Connect Onboarding (Complete Example)

```swift
// StripeConnectViewModel.swift
class StripeConnectViewModel: ObservableObject {
    @Published var onboardingStatus: OnboardingStatus = .loading
    @Published var accountLinkURL: URL?
    @Published var showSafari = false

    enum OnboardingStatus {
        case loading
        case notSetUp
        case pendingVerification
        case active
        case failed(String)
    }

    @MainActor
    func checkOnboardingStatus() async {
        do {
            let contractor = try await DriverAPIClient.shared.getCurrentContractor()

            if contractor.stripeConnectId == nil {
                onboardingStatus = .notSetUp
            } else if contractor.chargesEnabled == true {
                onboardingStatus = .active
            } else {
                onboardingStatus = .pendingVerification
            }
        } catch {
            onboardingStatus = .failed(error.localizedDescription)
        }
    }

    @MainActor
    func startOnboarding() async {
        do {
            // Generate account link on backend
            let response = try await DriverAPIClient.shared.createConnectAccountLink()

            guard let url = URL(string: response.accountLinkURL) else {
                onboardingStatus = .failed("Invalid onboarding URL")
                return
            }

            accountLinkURL = url
            showSafari = true

        } catch {
            onboardingStatus = .failed("Failed to start onboarding: \(error.localizedDescription)")
        }
    }
}

// StripeConnectOnboardingView.swift
struct StripeConnectOnboardingView: View {
    @StateObject private var viewModel = StripeConnectViewModel()
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(spacing: DriverSpacing.xl) {
            Image(systemName: "creditcard.circle")
                .font(.system(size: 80))
                .foregroundColor(.driverPrimary)

            Text("Set Up Payments")
                .font(DriverTypography.h1)

            Text("Connect your bank account to receive earnings from completed jobs.")
                .font(DriverTypography.body)
                .foregroundColor(.driverTextSecondary)
                .multilineTextAlignment(.center)

            Button("Connect with Stripe") {
                Task {
                    await viewModel.startOnboarding()
                }
            }
            .buttonStyle(DriverPrimaryButtonStyle())
        }
        .padding(DriverSpacing.xl)
        .sheet(isPresented: $viewModel.showSafari) {
            if let url = viewModel.accountLinkURL {
                SafariView(url: url)
                    .onDisappear {
                        Task {
                            await viewModel.checkOnboardingStatus()
                            if case .active = viewModel.onboardingStatus {
                                appState.hasCompletedStripeOnboarding = true
                            }
                        }
                    }
            }
        }
        .task {
            await viewModel.checkOnboardingStatus()
        }
    }
}
```

### Backend: Driver Payout Trigger

```python
# routes/payments.py
@payments_bp.route("/payout/<job_id>", methods=["POST"])
@require_auth
def trigger_payout(user_id, job_id):
    """Trigger payout to driver after job completion."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Verify job is completed
    if job.status != "completed":
        return jsonify({"error": "Job must be completed before payout"}), 400

    payment = job.payment
    if not payment:
        return jsonify({"error": "No payment record"}), 404

    # Check payment succeeded
    if payment.payment_status != "succeeded":
        return jsonify({"error": "Payment not succeeded"}), 409

    # Prevent duplicate payouts
    if payment.payout_status == "paid":
        return jsonify({"error": "Payout already completed"}), 409

    contractor = db.session.get(Contractor, job.driver_id)
    if not contractor or not contractor.stripe_connect_id:
        return jsonify({"error": "Driver not connected to Stripe"}), 400

    stripe = _get_stripe()

    try:
        # Create Stripe Transfer
        stripe.Transfer.create(
            amount=int(payment.driver_payout_amount * 100),
            currency="usd",
            destination=contractor.stripe_connect_id,
            metadata={"job_id": job_id},
        )

        payment.payout_status = "paid"
        payment.updated_at = utcnow()

        # Notify driver
        notification = Notification(
            id=generate_uuid(),
            user_id=contractor.user_id,
            type="payment",
            title="Payout Sent",
            body=f"${payment.driver_payout_amount:.2f} has been sent to your account.",
            data={"job_id": job_id, "amount": payment.driver_payout_amount},
        )
        db.session.add(notification)
        db.session.commit()

        return jsonify({"success": True, "payment": payment.to_dict()}), 200

    except Exception as e:
        payment.payout_status = "failed"
        db.session.commit()
        return jsonify({"error": f"Payout failed: {str(e)}"}), 502
```

### Backend: Earnings History Endpoint (NEW)

```python
# routes/payments.py
@payments_bp.route("/earnings/history", methods=["GET"])
@require_auth
def get_earnings_history(user_id):
    """Return detailed earnings history for a driver."""
    contractor = Contractor.query.filter_by(user_id=user_id).first()
    if not contractor:
        return jsonify({"error": "Contractor profile not found"}), 404

    # Get all payments for driver's completed jobs
    payments = (
        Payment.query
        .join(Job, Payment.job_id == Job.id)
        .filter(
            Job.driver_id == contractor.id,
            Payment.payment_status == "succeeded"
        )
        .order_by(Payment.created_at.desc())
        .all()
    )

    # Format entries
    entries = []
    for payment in payments:
        job = db.session.get(Job, payment.job_id)
        entries.append({
            "id": payment.id,
            "job_id": job.id,
            "address": job.address or "Unknown",
            "amount": payment.driver_payout_amount,
            "date": payment.created_at.isoformat() if payment.created_at else None,
            "payout_status": payment.payout_status,
        })

    return jsonify({"success": True, "entries": entries}), 200
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom card forms with manual validation | Stripe Payment Sheet with Apple Pay | 2020 (Payment Sheet GA) | Reduces development time from weeks to days, handles PCI compliance automatically |
| Separate Apple Pay and card flows | Unified Payment Sheet | 2020 | Single integration supports 40+ payment methods (cards, Apple Pay, Link, BNPL) |
| Manual KYC document collection | Stripe Connect hosted onboarding | 2018 (Connect platform launch) | Offloads legal compliance, identity verification, and international support to Stripe |
| Destination charges (funds go to connected account first) | Separate charges and transfers | 2019 (recommended pattern shift) | Platform retains control of funds, enables refunds without connected account balance |
| Manual payout scheduling with cron jobs | Stripe automatic payouts + Transfer API | 2017 | Stripe handles ACH timing, bank holidays, and failed transfer retries |

**Deprecated/outdated:**
- **Stripe Tokens API:** Replaced by PaymentMethods API (2019) — tokens are single-use, PaymentMethods support saving for future use
- **Charges API:** Replaced by PaymentIntents API (2019) — PaymentIntents handle SCA (3D Secure) and async payment flows
- **Bitcoin payments:** Deprecated (2018) — high volatility and regulatory concerns led Stripe to remove crypto support

---

## Open Questions

1. **Escrow release timing: automatic or manual?**
   - What we know: Backend has manual payout trigger (`POST /api/payments/payout/{job_id}`) but no automatic scheduler
   - What's unclear: Should payouts trigger immediately on job completion, or require admin approval for first X jobs?
   - Recommendation: Start with automatic payout on `job.status = "completed"` for MVP, add fraud detection thresholds later (e.g., hold payouts for drivers with <10 completed jobs)

2. **Driver onboarding: can they skip temporarily during testing?**
   - What we know: Context requires mandatory onboarding before app access
   - What's unclear: How to handle TestFlight testers without real bank accounts
   - Recommendation: Add `ENABLE_STRIPE_CONNECT_REQUIREMENT` env var (default `true`), set to `false` for TestFlight beta builds only

3. **Payment confirmation UI: overlay or full-screen?**
   - What we know: Phase 2 uses success overlay (`BookingSuccessView`) with job ID display
   - What's unclear: Should payment success reuse existing overlay, or introduce new design?
   - Recommendation: Reuse existing overlay pattern — add "Payment confirmed" badge above job ID, maintain visual consistency

4. **Earnings dashboard: paginated or all-time scroll?**
   - What we know: User wants "full earnings history (all time)" with date filters
   - What's unclear: Performance implications if driver has 500+ completed jobs
   - Recommendation: Start with unpaginated API (most drivers have <100 jobs in first 6 months), add pagination if response exceeds 5s or 10MB

5. **Apple Pay merchant certificate: Stripe-managed or manual?**
   - What we know: Payment Sheet config references `merchant.com.goumuve.app`
   - What's unclear: Is certificate already uploaded to Stripe Dashboard, or does this need setup?
   - Recommendation: Verify in Stripe Dashboard → Settings → Apple Pay → merchant.com.goumuve.app exists, if not, Stripe auto-generates CSR and syncs with Apple

---

## Sources

### Primary (HIGH confidence)

- [Stripe iOS SDK Documentation](https://docs.stripe.com/sdks/ios) - Official SDK requirements, installation, API reference
- [Accept a payment with Payment Sheet (iOS)](https://docs.stripe.com/payments/accept-a-payment?platform=ios&ui=payment-sheet) - Complete Payment Sheet integration guide
- [Stripe Connect Hosted Onboarding](https://docs.stripe.com/connect/hosted-onboarding) - Account link generation, return URL handling, SFSafariViewController implementation
- [Place a hold on a payment method](https://docs.stripe.com/payments/place-a-hold-on-a-payment-method) - Manual capture, authorization windows, escrow mechanics
- [Stripe iOS GitHub Repository](https://github.com/stripe/stripe-ios) - Latest release (25.6.0), Swift Package Manager support
- [Stripe webhook signature verification](https://docs.stripe.com/webhooks/signature) - Raw body requirement, replay attack prevention

### Secondary (MEDIUM confidence)

- [Stripe Connect marketplace payments overview](https://www.sharetribe.com/academy/marketplace-payments/stripe-connect-overview/) - Commission splits, payout timing
- [Rocket Rides sample app](https://github.com/stripe/stripe-connect-rocketrides) - Reference implementation for on-demand marketplace
- [Payment retry guide for merchants](https://www.checkout.com/blog/payment-retries-guide) - Hard vs soft declines, cost considerations
- [Guide to Stripe Webhooks](https://hookdeck.com/webhooks/platforms/guide-to-stripe-webhooks-features-and-best-practices) - Best practices, security measures

### Tertiary (LOW confidence)

- [Medium: Stripe Connect onboarding iOS implementation](https://medium.com/swlh/implementing-stripe-onboarding-to-your-ios-project-swift-firebase-node-js-f855965a3ce5) - Practical iOS example (2020)
- [Medium: SwiftUI payment process view](https://medium.com/@aeiosdev/swiftui-creating-a-card-payment-process-view-3e50f6e2f50) - Custom UI patterns (reference only, not used)

### Existing Codebase (HIGH confidence)

- `/JunkOS-Clean/JunkOS/Services/PaymentService.swift` - Existing PaymentIntent creation, Apple Pay support
- `/backend/routes/payments.py` - Existing endpoints: `/create-intent-simple`, `/confirm-simple`, `/earnings`, `/payout/{job_id}`
- `/backend/models.py` - Payment model: `driver_payout_amount`, `payout_status` (pending/processing/paid), commission structure
- `/JunkOS-Driver/Views/Earnings/EarningsView.swift` - Existing UI structure, segmented control pattern
- `/JunkOS-Driver/Models/EarningsModels.swift` - EarningsSummary, EarningsEntry data models

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Stripe iOS SDK 25.6.0 is latest stable, official documentation current as of 2026-01-28
- Architecture: HIGH - Payment Sheet + hosted onboarding are recommended patterns from Stripe, existing backend aligns
- Pitfalls: MEDIUM - Based on common marketplace issues (webhook verification, escrow timing) but not all project-specific
- Code examples: HIGH - Verified against Stripe docs and existing codebase (PaymentService.swift, routes/payments.py)

**Research date:** 2026-02-14
**Valid until:** 2026-03-16 (30 days — Stripe iOS SDK stable, quarterly updates expected)
