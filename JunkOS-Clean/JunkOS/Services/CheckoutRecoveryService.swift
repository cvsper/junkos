//
//  CheckoutRecoveryService.swift
//  Umuve
//
//  Finishes checkouts that were interrupted after the card was charged
//  (audit F05).
//
//  Two rules drive everything here:
//
//    1. A lost HTTP response is NOT a failed payment. If Stripe said the
//       charge completed, the only correct behaviour is to keep telling our
//       server so — with backoff — and, when that finally gives up, to tell
//       the customer the money arrived and hand them a job number. Showing
//       "payment failed" because a POST timed out is what F05 is about.
//    2. Never re-charge to recover. The pending record carries the job id and
//       the submission key, so resuming is always confirm-or-read, never a
//       second PaymentIntent.
//

import Foundation

@MainActor
final class CheckoutRecoveryService: ObservableObject {

    enum State: Equatable {
        case idle
        /// A paid-but-unconfirmed booking is being reconciled in the
        /// background. Surfaces as "Finishing your booking…".
        case finishing(jobId: String)
        case succeeded(jobId: String)
        /// Retries are exhausted. The customer paid; a human has to close it.
        case needsSupport(jobId: String, message: String)
    }

    static let shared = CheckoutRecoveryService()

    @Published private(set) var state: State = .idle

    private let api: BookingCheckoutAPI
    private let store: PendingBookingStoring
    /// Injected so tests don't actually wait out the backoff.
    private let sleeper: (UInt64) async -> Void
    private var isWorking = false

    init(api: BookingCheckoutAPI = APIClient.shared,
         store: PendingBookingStoring = PendingBookingStore.shared,
         sleeper: @escaping (UInt64) async -> Void = { ns in
             _ = try? await Task.sleep(nanoseconds: ns)
         }) {
        self.api = api
        self.store = store
        self.sleeper = sleeper
    }

    // MARK: - Entry points

    /// Called on launch and whenever the booking wizard opens. Cheap and
    /// silent when there is nothing to recover.
    func resumeIfNeeded() async {
        guard !isWorking else { return }
        guard let pending = store.load() else {
            state = .idle
            return
        }

        if pending.isStale() {
            // An unpaid booking nobody came back to. Dropping the local record
            // does not touch the server row — it just stops us resuming a cart
            // the customer has long since abandoned.
            store.clear()
            state = .idle
            return
        }

        if pending.isPaid {
            _ = await confirmPaidBooking(pending)
            return
        }

        // Not known-paid. It may still have settled via Apple Pay / the Stripe
        // webhook after we lost the app, so ask before assuming it didn't.
        isWorking = true
        defer { isWorking = false }
        state = .finishing(jobId: pending.jobId)
        do {
            let snapshot = try await api.fetchBookingStatus(jobId: pending.jobId)
            if snapshot.isSettled {
                store.clear()
                state = .succeeded(jobId: pending.jobId)
            } else if snapshot.isDead {
                store.clear()
                state = .idle
            } else {
                // The booking exists and is unpaid — the wizard picks it back
                // up and reuses it instead of creating a second job.
                state = .idle
            }
        } catch {
            // A status check must never block the app or scare the customer.
            state = .idle
        }
    }

    /// Confirm a charge Stripe already accepted. Retries transient failures
    /// with exponential backoff, then falls back to reading the booking (the
    /// webhook may have settled it while we were failing to reach /confirm).
    @discardableResult
    func confirmPaidBooking(_ pending: PendingBooking,
                            maxAttempts: Int = 5) async -> Result<String, CheckoutAPIError> {
        isWorking = true
        defer { isWorking = false }

        // Persist ".paid" before anything else so a crash mid-retry still
        // resumes as a confirmation, not as a fresh payment.
        var record = pending
        record.stage = .paid
        store.save(record)
        state = .finishing(jobId: record.jobId)

        guard let intentId = record.paymentIntentId else {
            // Stripe completed but we never stored the intent — the booking
            // read is the only truth left.
            if await settledOnServer(record.jobId) { return .success(record.jobId) }
            let error = CheckoutAPIError(
                statusCode: 0, code: "missing_intent",
                message: "We couldn't match your payment to this booking automatically."
            )
            state = .needsSupport(jobId: record.jobId, message: Self.supportMessage(record))
            return .failure(error)
        }

        var delay: UInt64 = 500_000_000     // 0.5s, doubling: 0.5/1/2/4s
        var lastError = CheckoutAPIError(statusCode: 0, message: "Confirmation did not complete.")

        for attempt in 1...max(1, maxAttempts) {
            do {
                _ = try await api.confirmPayment(paymentIntentId: intentId, bookingId: record.jobId)
                store.clear()
                state = .succeeded(jobId: record.jobId)
                return .success(record.jobId)
            } catch let error as CheckoutAPIError {
                lastError = error
                // The server already considers this booking paid — that is a
                // success from the customer's point of view.
                if error.code == "already_paid" {
                    store.clear()
                    state = .succeeded(jobId: record.jobId)
                    return .success(record.jobId)
                }
                if !error.isRetryable { break }
            } catch {
                lastError = CheckoutAPIError.transport(error)
            }

            if attempt < max(1, maxAttempts) {
                await sleeper(delay)
                delay *= 2
            }
        }

        // Last resort before bothering anyone: maybe the Stripe webhook beat
        // us to it and the booking is already confirmed server-side.
        if await settledOnServer(record.jobId) { return .success(record.jobId) }

        state = .needsSupport(jobId: record.jobId, message: Self.supportMessage(record))
        return .failure(lastError)
    }

    /// Drop a terminal banner once the customer has seen it.
    func acknowledge() {
        switch state {
        case .succeeded, .needsSupport:
            state = .idle
        case .idle, .finishing:
            break
        }
    }

    // MARK: - Helpers

    private func settledOnServer(_ jobId: String) async -> Bool {
        guard let snapshot = try? await api.fetchBookingStatus(jobId: jobId), snapshot.isSettled else {
            return false
        }
        store.clear()
        state = .succeeded(jobId: jobId)
        return true
    }

    /// Deliberately never says "payment failed" — by the time we are here the
    /// charge has been accepted by Stripe.
    static func supportMessage(_ record: PendingBooking) -> String {
        let reference = record.confirmationCode ?? String(record.jobId.prefix(8)).uppercased()
        return """
        Your payment went through. We're still finishing the booking on our side.
        Keep reference \(reference) — if you don't get a confirmation shortly, \
        contact support with it and we'll sort it out. You have not been charged twice.
        """
    }
}
