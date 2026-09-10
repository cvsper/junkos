//
//  BookingReviewViewModel.swift
//  Umuve
//
//  Book first, pay second (audit F05).
//
//  The old order was: create a PaymentIntent for a loose dollar amount →
//  charge the card → try to confirm it → try to create a job. Every step
//  after the charge could fail, and two of them always did: /confirm 404'd
//  because no Payment row existed for a booking-less intent, and the job
//  create targeted a route the backend didn't implement. A customer could pay
//  and end up with nothing, and retrying risked a second charge.
//
//  The order now is:
//    1. re-quote against the server with the full cart, coordinates and slot
//    2. POST /api/booking            → Job + Payment + checkout_token
//    3. persist that record locally  → survives app death
//    4. create ONE payment attempt for that job (idempotent submission key)
//    5. present the Stripe sheet
//    6. on completion, mark ".paid" locally BEFORE any network call, then
//       confirm with retries
//    7. clear the local record only once the server has confirmed
//

import Foundation
import SwiftUI
import StripePaymentSheet

@MainActor
final class BookingReviewViewModel: ObservableObject {

    /// Where the checkout is. Drives button state and the status banner.
    enum Phase: Equatable {
        case idle
        /// Asking the server what this cart actually costs.
        case quoting
        /// Creating the Job. Nothing has been charged.
        case booking
        /// Creating / resuming the payment attempt for that job.
        case preparingPayment
        /// The Stripe sheet is up.
        case awaitingPayment
        /// The card went through; telling our server about it.
        case confirming
        case done
    }

    // MARK: - Published state

    @Published var phase: Phase = .idle
    @Published var errorMessage: String?
    /// Non-alarming progress copy ("Payment received — confirming…").
    @Published var statusMessage: String?
    /// Set only when a *paid* booking couldn't be confirmed. Never set for an
    /// ordinary payment failure.
    @Published var supportReference: String?
    @Published var showSuccess = false
    @Published var createdJobId: String?
    @Published var confirmationCode: String?
    @Published var paymentSheet: PaymentSheet?

    /// Kept for the existing view bindings.
    var isPreparingPayment: Bool {
        phase == .quoting || phase == .booking || phase == .preparingPayment
    }
    var isSubmitting: Bool { phase == .confirming }
    var isBusy: Bool { phase != .idle && phase != .done }

    // MARK: - Collaborators

    private let api: BookingCheckoutAPI
    private let store: PendingBookingStoring
    private let recovery: CheckoutRecoveryService
    private let sleeper: (UInt64) async -> Void

    /// In-memory mirror of the persisted record for the current attempt.
    private var pending: PendingBooking?

    init(api: BookingCheckoutAPI = APIClient.shared,
         store: PendingBookingStoring = PendingBookingStore.shared,
         recovery: CheckoutRecoveryService = .shared,
         sleeper: @escaping (UInt64) async -> Void = { ns in
             _ = try? await Task.sleep(nanoseconds: ns)
         }) {
        self.api = api
        self.store = store
        self.recovery = recovery
        self.sleeper = sleeper
    }

    // MARK: - Entry point

    /// "Pay" on the review step. Books, then pays.
    func confirmAndPay(bookingData: BookingData) async {
        guard !isBusy else { return }
        errorMessage = nil
        supportReference = nil

        guard bookingData.serviceType != nil else {
            errorMessage = "Service type is required"
            return
        }
        guard bookingData.isAddressValid else {
            errorMessage = "Valid address is required"
            return
        }
        guard bookingData.hasItems else {
            errorMessage = "Add at least one item so we can price your pickup."
            return
        }
        guard let selectedDate = bookingData.selectedDate,
              let selectedTimeSlot = bookingData.selectedTimeSlot else {
            errorMessage = "Please select a date and time"
            return
        }

        let scheduledDate = Self.apiDateString(selectedDate)
        let scheduledTime = Self.apiTimeString(fromSlotId: selectedTimeSlot)

        // A previously-paid record must be reconciled, never re-charged.
        if let existing = store.load(), existing.isPaid {
            await finishPaidBooking(existing, bookingData: bookingData)
            return
        }

        do {
            // (a) Server price for the full cart, coordinates and schedule.
            phase = .quoting
            await refreshServerPrice(bookingData: bookingData, scheduledDate: scheduledDate)

            // (b) Book first.
            let record = try await ensureBooking(
                bookingData: bookingData,
                scheduledDate: scheduledDate,
                scheduledTime: scheduledTime
            )

            // (c) Then create (or resume) the one payment attempt for it.
            phase = .preparingPayment
            let intent = try await requestIntent(for: record, bookingData: bookingData)

            // (d) Present Stripe with a secret tied to a real booking.
            phase = .awaitingPayment
            paymentSheet = PaymentService.shared.makePaymentSheet(clientSecret: intent.clientSecret)
        } catch let error as CheckoutAPIError {
            phase = .idle
            errorMessage = Self.friendlyMessage(for: error)
            Self.haptic(.error)
        } catch {
            phase = .idle
            errorMessage = error.localizedDescription
            Self.haptic(.error)
        }
    }

    // MARK: - Stripe result

    func handlePaymentResult(_ result: PaymentSheetResult, bookingData: BookingData) async {
        paymentSheet = nil

        switch result {
        case .completed:
            guard let record = pending ?? store.load() else {
                // Should be unreachable: the record is written before the
                // sheet can appear. Don't claim failure over a paid card.
                phase = .idle
                statusMessage = nil
                errorMessage = """
                Your payment went through, but we lost track of the booking on this device. \
                Please contact support@goumuve.com before paying again.
                """
                return
            }
            await finishPaidBooking(record, bookingData: bookingData)

        case .canceled:
            // The booking exists and is unpaid. Tapping Pay again reuses it
            // and the same submission key, so no duplicate job or charge.
            phase = .idle
            statusMessage = nil

        case .failed(let error):
            // A genuine card failure — the only case that may say "failed".
            phase = .idle
            statusMessage = nil
            errorMessage = "Payment failed: \(error.localizedDescription)"
            Self.haptic(.error)
        }
    }

    // MARK: - Recovery

    /// Called when the review step appears. Picks up a checkout that was
    /// interrupted, without ever asking for payment twice.
    func resumePendingBookingIfNeeded(bookingData: BookingData) async {
        guard !isBusy else { return }
        guard let record = store.load() else { return }

        if record.isStale() {
            store.clear()
            return
        }
        if record.isPaid {
            await finishPaidBooking(record, bookingData: bookingData)
            return
        }

        // Unpaid but real: it may have settled through the Stripe webhook
        // while the app was gone. Check before letting the user pay again.
        pending = record
        createdJobId = record.jobId
        confirmationCode = record.confirmationCode
        if let snapshot = try? await api.fetchBookingStatus(jobId: record.jobId) {
            if snapshot.isSettled {
                store.clear()
                pending = nil
                markSucceeded(jobId: record.jobId, bookingData: bookingData)
            } else if snapshot.isDead {
                store.clear()
                pending = nil
                createdJobId = nil
            }
        }
    }

    /// Confirm a charge Stripe accepted. Persists ".paid" first, then retries.
    private func finishPaidBooking(_ record: PendingBooking, bookingData: BookingData) async {
        var paid = record
        paid.stage = .paid
        store.save(paid)
        pending = paid
        createdJobId = paid.jobId
        confirmationCode = paid.confirmationCode

        phase = .confirming
        errorMessage = nil
        statusMessage = "Payment received — confirming your booking…"

        let outcome = await recovery.confirmPaidBooking(paid)
        statusMessage = nil

        switch outcome {
        case .success(let jobId):
            markSucceeded(jobId: jobId, bookingData: bookingData)
        case .failure:
            // Retries exhausted. The money moved; say so, and hand over a
            // reference. Never the words "payment failed".
            phase = .idle
            supportReference = paid.confirmationCode ?? String(paid.jobId.prefix(8)).uppercased()
            errorMessage = CheckoutRecoveryService.supportMessage(paid)
        }
    }

    private func markSucceeded(jobId: String, bookingData: BookingData) {
        pending = nil
        createdJobId = jobId
        phase = .done
        statusMessage = nil
        errorMessage = nil
        supportReference = nil
        showSuccess = true
        Self.haptic(.success)
    }

    // MARK: - Steps

    /// Show the price the server will actually charge, not a local guess.
    private func refreshServerPrice(bookingData: BookingData, scheduledDate: String) async {
        do {
            let estimate = try await APIClient.shared.getPricingEstimate(
                items: bookingData.items,
                pickupLat: bookingData.pickupCoordinate?.latitude,
                pickupLng: bookingData.pickupCoordinate?.longitude,
                scheduledDate: scheduledDate
            )
            bookingData.estimatedPrice = estimate.total
            bookingData.priceBreakdown = estimate
        } catch {
            // Non-fatal: the booking call recomputes the price server-side and
            // the payment amount is derived from the Job, never from here.
            print("[checkout] estimate refresh failed: \(error)")
        }
    }

    /// Reuse the booking already created for this exact cart, or create one.
    private func ensureBooking(bookingData: BookingData,
                               scheduledDate: String,
                               scheduledTime: String) async throws -> PendingBooking {
        let fingerprint = Self.fingerprint(bookingData: bookingData,
                                           date: scheduledDate,
                                           time: scheduledTime)

        if let existing = store.load(), !existing.isStale(), !existing.isPaid,
           existing.cartFingerprint == fingerprint {
            pending = existing
            createdJobId = existing.jobId
            confirmationCode = existing.confirmationCode
            return existing
        }

        phase = .booking

        // Photos are best-effort: a failed upload must not cost the booking.
        var photoURLs: [String] = []
        if !bookingData.photos.isEmpty {
            photoURLs = (try? await APIClient.shared.uploadPhotos(bookingData.photos)) ?? []
        }

        let localTotal = max(0, (bookingData.estimatedPrice ?? 0) - bookingData.promoDiscount)
        let request = BookingSubmitRequest(
            address: bookingData.address.fullAddress,
            lat: bookingData.pickupCoordinate?.latitude,
            lng: bookingData.pickupCoordinate?.longitude,
            items: bookingData.items.map {
                BookingItemPayload(category: $0.category.apiKey, quantity: $0.quantity, size: "medium")
            },
            photoURLs: photoURLs,
            scheduledDate: scheduledDate,
            scheduledTime: scheduledTime,
            estimatedPrice: localTotal,
            notes: bookingData.notes.isEmpty ? nil : bookingData.notes,
            promoCode: bookingData.promoApplied ? bookingData.promoCode : nil,
            priceVersion: bookingData.priceBreakdown?.priceVersion
        )

        let response = try await api.submitBooking(request)

        let record = PendingBooking(
            jobId: response.jobId,
            submissionKey: UUID().uuidString,
            checkoutToken: response.checkoutToken,
            confirmationCode: response.confirmationCode,
            paymentIntentId: nil,
            amount: response.totalPrice ?? localTotal,
            stage: .booked,
            createdAt: Date(),
            cartFingerprint: fingerprint
        )
        // Written before any charge is possible — this is the record that
        // makes a crash on the next line survivable.
        store.save(record)
        pending = record
        createdJobId = record.jobId
        confirmationCode = record.confirmationCode
        return record
    }

    /// Create (or resume) the payment attempt. The server answers 409 with a
    /// `code` for the recoverable cases; we re-quote or wait accordingly.
    private func requestIntent(for record: PendingBooking,
                               bookingData: BookingData) async throws -> CheckoutIntentResponse {
        var working = record
        var lastError: CheckoutAPIError?

        for attempt in 0..<3 {
            do {
                let intent = try await api.createPaymentIntent(
                    bookingId: working.jobId,
                    submissionKey: working.submissionKey,
                    checkoutToken: working.checkoutToken,
                    amount: working.amount,
                    customerEmail: nil,
                    promoCode: bookingData.promoApplied ? bookingData.promoCode : nil,
                    priceVersion: bookingData.priceBreakdown?.priceVersion
                )
                working.paymentIntentId = intent.paymentIntentId
                working.amount = intent.amount ?? working.amount
                working.stage = .intentCreated
                store.save(working)
                pending = working
                return intent
            } catch let error as CheckoutAPIError {
                lastError = error
                switch error.code {
                case "amount_changed", "submission_key_used", "price_version_stale":
                    // The quote moved (or that key is spent). Re-quote and
                    // start a fresh attempt series — never silently pay the
                    // old number.
                    await refreshServerPrice(
                        bookingData: bookingData,
                        scheduledDate: Self.apiDateString(bookingData.selectedDate ?? Date())
                    )
                    working.submissionKey = UUID().uuidString
                    working.amount = max(0, (bookingData.estimatedPrice ?? working.amount)
                                            - bookingData.promoDiscount)
                    store.save(working)
                    pending = working
                case "attempt_in_progress":
                    let seconds = UInt64(max(1, error.retryAfter ?? 2))
                    await sleeper(seconds * 1_000_000_000)
                case "already_paid":
                    // Someone (a webhook, another device) already settled it.
                    throw error
                default:
                    throw error
                }
                if attempt == 2 { throw error }
            }
        }

        throw lastError ?? CheckoutAPIError(
            statusCode: 0, message: "We couldn't start the payment. Please try again."
        )
    }

    // MARK: - Formatting helpers

    /// "yyyy-MM-dd". POSIX locale so a non-Gregorian device calendar can't
    /// produce a date the backend rejects.
    static func apiDateString(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }

    /// Slot ids encode the start hour: "8-10" → "08:00".
    static func apiTimeString(fromSlotId slotId: String) -> String {
        let startHourPart = slotId.components(separatedBy: "-").first ?? "9"
        let startHour = Int(startHourPart) ?? 9
        return String(format: "%02d:00", startHour)
    }

    /// Identifies the cart a booking was created from. If any of this changes
    /// the customer is buying something else, so the old job is not reused.
    static func fingerprint(bookingData: BookingData, date: String, time: String) -> String {
        let items = bookingData.items
            .map { "\($0.category.apiKey)x\($0.quantity)" }
            .sorted()
            .joined(separator: ",")
        let coordinate = bookingData.pickupCoordinate
            .map { String(format: "%.5f,%.5f", $0.latitude, $0.longitude) } ?? "-"
        let promo = bookingData.promoApplied ? bookingData.promoCode : ""
        return [bookingData.address.fullAddress, coordinate, items, date, time, promo]
            .joined(separator: "|")
    }

    static func friendlyMessage(for error: CheckoutAPIError) -> String {
        switch error.code {
        case "already_paid":
            return "This booking is already paid. Check Orders for its status."
        case "booking_cancelled":
            return "This booking was cancelled. Start a new one to book again."
        case "network":
            return "We couldn't reach Umuve. Check your connection and try again — you have not been charged."
        default:
            return error.message
        }
    }

    private static func haptic(_ type: UINotificationFeedbackGenerator.FeedbackType) {
        UINotificationFeedbackGenerator().notificationOccurred(type)
    }
}
