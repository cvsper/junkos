//
//  BookingCheckoutAPI.swift
//  Umuve
//
//  The book-first / pay-second checkout contract (audit F05).
//
//  Field names here are copied from the Flask handlers, not guessed:
//    * POST /api/booking          → backend/routes/booking.py create_booking()
//    * POST /api/payments/create-intent-simple
//                                 → backend/routes/payments.py
//                                   create_simple_payment_intent()
//    * POST /api/payments/confirm-simple
//                                 → backend/routes/payments.py
//                                   confirm_simple_payment()
//    * GET  /api/booking/<job_id> → backend/routes/booking.py
//                                   get_booking_status()
//
//  This mirrors what the production web client does in
//  platform/src/components/booking/step-6-payment.tsx: submit the booking,
//  take the checkout_token back, then create ONE payment attempt per
//  submission key, then confirm that intent against the job.
//

import Foundation

// MARK: - Request payloads

/// One line of the cart, in the shape `calculate_estimate()` reads:
/// `{ "category": ..., "quantity": ..., "size": ... }`.
struct BookingItemPayload: Codable, Equatable {
    let category: String
    let quantity: Int
    let size: String?

    init(category: String, quantity: Int, size: String? = nil) {
        self.category = category
        self.quantity = quantity
        self.size = size
    }
}

/// Body for POST /api/booking. Sent snake_case because that is what
/// `create_booking()` reads first for every field.
struct BookingSubmitRequest: Equatable {
    /// Flattened one-line address. Sent as a STRING deliberately: when
    /// `address` is a dict the backend collapses it to `street` alone and the
    /// city/zip are lost.
    var address: String
    var lat: Double?
    var lng: Double?
    var items: [BookingItemPayload]
    /// URLs from POST /api/upload/photos — never raw image data.
    var photoURLs: [String]
    /// "yyyy-MM-dd", Florida wall clock. `parse_local()` converts to UTC.
    var scheduledDate: String
    /// "HH:mm" (or a slot id like "8-10" — `normalize_slot()` accepts both).
    var scheduledTime: String
    /// Advisory only. The server recomputes the total and charges its own.
    var estimatedPrice: Double
    var notes: String?
    var promoCode: String?
    /// Forwarded when the estimate endpoint starts returning one. The backend
    /// ignores unknown fields today, so sending it early is free.
    var priceVersion: String?
    var customerName: String?
    var customerEmail: String?
    var customerPhone: String?
    var leadSource: String = "ios_app"

    func jsonObject() -> [String: Any] {
        var body: [String: Any] = [
            "address": address,
            "items": items.map { item -> [String: Any] in
                var line: [String: Any] = [
                    "category": item.category,
                    "quantity": item.quantity,
                ]
                if let size = item.size { line["size"] = size }
                return line
            },
            "photos": photoURLs,
            "scheduled_date": scheduledDate,
            "scheduled_time": scheduledTime,
            "estimated_price": estimatedPrice,
            "lead_source": leadSource,
        ]
        if let lat { body["lat"] = lat }
        if let lng { body["lng"] = lng }
        if let notes, !notes.isEmpty { body["notes"] = notes }
        if let promoCode, !promoCode.isEmpty { body["promo_code"] = promoCode }
        if let priceVersion, !priceVersion.isEmpty { body["price_version"] = priceVersion }
        if let customerName, !customerName.isEmpty { body["customerName"] = customerName }
        if let customerEmail, !customerEmail.isEmpty { body["customerEmail"] = customerEmail }
        if let customerPhone, !customerPhone.isEmpty { body["customerPhone"] = customerPhone }
        return body
    }
}

// MARK: - Response payloads

/// POST /api/booking → `{ success, job: {...}, payment: {...}, checkout_token }`
struct BookingSubmitResponse: Decodable, Equatable {
    let jobId: String
    let confirmationCode: String?
    let totalPrice: Double?
    let checkoutToken: String?

    private enum CodingKeys: String, CodingKey {
        case success, job
        case checkoutToken = "checkout_token"
        // POST /api/jobs (routes/jobs.py) flattens these alongside `job`.
        case jobId = "job_id"
        case confirmationCode = "confirmation_code"
    }

    private struct JobPayload: Decodable {
        let id: String?
        let confirmationCode: String?
        let totalPrice: Double?

        private enum CodingKeys: String, CodingKey {
            case id
            case confirmationCode = "confirmation_code"
            case totalPrice = "total_price"
        }
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let job: JobPayload? = (try? c.decodeIfPresent(JobPayload.self, forKey: .job)) ?? nil
        let flatId: String? = (try? c.decodeIfPresent(String.self, forKey: .jobId)) ?? nil
        let flatCode: String? = (try? c.decodeIfPresent(String.self, forKey: .confirmationCode)) ?? nil

        guard let id = job?.id ?? flatId, !id.isEmpty else {
            throw DecodingError.dataCorruptedError(
                forKey: .job, in: c,
                debugDescription: "Booking response carried no job id"
            )
        }
        jobId = id
        confirmationCode = job?.confirmationCode ?? flatCode
        totalPrice = job?.totalPrice
        checkoutToken = (try? c.decodeIfPresent(String.self, forKey: .checkoutToken)) ?? nil
    }

    init(jobId: String, confirmationCode: String?, totalPrice: Double?, checkoutToken: String?) {
        self.jobId = jobId
        self.confirmationCode = confirmationCode
        self.totalPrice = totalPrice
        self.checkoutToken = checkoutToken
    }
}

/// POST /api/payments/create-intent-simple → camelCase keys straight from Flask.
struct CheckoutIntentResponse: Decodable, Equatable {
    let clientSecret: String
    let paymentIntentId: String
    let attemptId: String?
    /// true when the server handed back the intent it already minted for this
    /// submission key rather than creating a second payable one.
    let reused: Bool?
    let amount: Double?
}

/// POST /api/payments/confirm-simple → `{ success, payment: {...}, job: {...} }`
struct CheckoutConfirmResponse: Decodable, Equatable {
    let success: Bool
    let paymentStatus: String?
    let jobStatus: String?

    private enum CodingKeys: String, CodingKey { case success, payment, job }
    private struct PaymentPayload: Decodable {
        let paymentStatus: String?
        private enum CodingKeys: String, CodingKey { case paymentStatus = "payment_status" }
    }
    private struct JobPayload: Decodable { let status: String? }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let flag: Bool? = (try? c.decodeIfPresent(Bool.self, forKey: .success)) ?? nil
        let payment: PaymentPayload? = (try? c.decodeIfPresent(PaymentPayload.self, forKey: .payment)) ?? nil
        let job: JobPayload? = (try? c.decodeIfPresent(JobPayload.self, forKey: .job)) ?? nil
        success = flag ?? true
        paymentStatus = payment?.paymentStatus
        jobStatus = job?.status
    }

    init(success: Bool, paymentStatus: String?, jobStatus: String?) {
        self.success = success
        self.paymentStatus = paymentStatus
        self.jobStatus = jobStatus
    }
}

/// GET /api/booking/<job_id> → the recovery read. Enough to decide whether a
/// payment landed without asking the customer anything.
struct BookingStatusSnapshot: Decodable, Equatable {
    let jobId: String
    let status: String
    let paymentStatus: String?
    let totalPrice: Double?
    let confirmationCode: String?

    /// The money side is done — nothing left to confirm.
    var isSettled: Bool {
        guard let paymentStatus else { return false }
        return ["succeeded", "refunded", "partially_refunded"].contains(paymentStatus)
    }

    /// The booking can never be paid for; stop trying to resume it.
    var isDead: Bool {
        ["cancelled", "canceled"].contains(status)
    }

    private enum CodingKeys: String, CodingKey { case success, booking }
    private struct BookingPayload: Decodable {
        let id: String
        let status: String?
        let totalPrice: Double?
        let confirmationCode: String?
        let payment: PaymentPayload?

        struct PaymentPayload: Decodable {
            let paymentStatus: String?
            private enum CodingKeys: String, CodingKey { case paymentStatus = "payment_status" }
        }

        private enum CodingKeys: String, CodingKey {
            case id, status, payment
            case totalPrice = "total_price"
            case confirmationCode = "confirmation_code"
        }
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let booking = try c.decode(BookingPayload.self, forKey: .booking)
        jobId = booking.id
        status = booking.status ?? "unknown"
        paymentStatus = booking.payment?.paymentStatus
        totalPrice = booking.totalPrice
        confirmationCode = booking.confirmationCode
    }

    init(jobId: String, status: String, paymentStatus: String?,
         totalPrice: Double? = nil, confirmationCode: String? = nil) {
        self.jobId = jobId
        self.status = status
        self.paymentStatus = paymentStatus
        self.totalPrice = totalPrice
        self.confirmationCode = confirmationCode
    }
}

// MARK: - Errors

/// A checkout failure with enough structure to decide what to do next.
///
/// The backend answers 409 with a machine-readable `code` for every state the
/// client can actually recover from (`amount_changed`, `submission_key_used`,
/// `attempt_in_progress`, `already_paid`), so the app reacts to the code
/// rather than pattern-matching English.
struct CheckoutAPIError: LocalizedError, Equatable {
    /// 0 means the request never got an HTTP response (transport failure).
    let statusCode: Int
    let code: String?
    let message: String
    let retryAfter: Int?

    init(statusCode: Int, code: String? = nil, message: String, retryAfter: Int? = nil) {
        self.statusCode = statusCode
        self.code = code
        self.message = message
        self.retryAfter = retryAfter
    }

    var errorDescription: String? { message }

    /// Worth retrying the exact same call. A 4xx (other than 408/429) means
    /// the request itself is wrong, so retrying just burns time.
    var isRetryable: Bool {
        if statusCode == 0 { return true }              // transport / timeout
        if statusCode == 408 || statusCode == 429 { return true }
        return (500...599).contains(statusCode)
    }

    static func transport(_ error: Error) -> CheckoutAPIError {
        CheckoutAPIError(statusCode: 0, code: "network",
                         message: error.localizedDescription)
    }
}

/// Error envelope Flask returns: `{ "error": ..., "code": ..., "retry_after": ... }`.
struct CheckoutErrorBody: Decodable {
    let error: String?
    let message: String?
    let code: String?
    let retryAfter: Int?

    private enum CodingKeys: String, CodingKey {
        case error, message, code
        case retryAfter = "retry_after"
    }
}

// MARK: - Protocol

/// The four calls the wizard needs. A protocol so the checkout flow can be
/// unit-tested without a network (see JunkOSTests/Services).
protocol BookingCheckoutAPI: AnyObject {
    /// Step 1 — create the Job + Payment row. Nothing has been charged yet.
    func submitBooking(_ request: BookingSubmitRequest) async throws -> BookingSubmitResponse

    /// Step 2 — create (or resume) THE payment attempt for that job.
    func createPaymentIntent(
        bookingId: String,
        submissionKey: String,
        checkoutToken: String?,
        amount: Double,
        customerEmail: String?,
        promoCode: String?,
        priceVersion: String?
    ) async throws -> CheckoutIntentResponse

    /// Step 3 — tell the server the charge succeeded, against a known job.
    func confirmPayment(paymentIntentId: String, bookingId: String) async throws -> CheckoutConfirmResponse

    /// Recovery — did this booking end up paid while we weren't looking?
    func fetchBookingStatus(jobId: String) async throws -> BookingStatusSnapshot
}
