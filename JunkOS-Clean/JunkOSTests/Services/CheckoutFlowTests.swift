//
//  CheckoutFlowTests.swift
//  UmuveTests
//
//  Covers the two properties audit F05 turns on:
//    1. the pending-booking record survives a round trip through storage, so
//       a checkout interrupted after the charge can be resumed;
//    2. confirmation is RETRIED on transient failures instead of being
//       reported to the customer as a failed payment.
//

import XCTest
@testable import Umuve

// MARK: - Test doubles

/// In-memory store — no UserDefaults side effects between tests.
final class InMemoryPendingBookingStore: PendingBookingStoring {
    private(set) var saved: PendingBooking?
    private(set) var clearCount = 0

    init(seed: PendingBooking? = nil) { saved = seed }

    func load() -> PendingBooking? { saved }
    func save(_ booking: PendingBooking) { saved = booking }
    func clear() { saved = nil; clearCount += 1 }
}

final class StubCheckoutAPI: BookingCheckoutAPI {
    var submitResult: Result<BookingSubmitResponse, Error> = .failure(
        CheckoutAPIError(statusCode: 500, message: "not stubbed"))
    var intentResult: Result<CheckoutIntentResponse, Error> = .failure(
        CheckoutAPIError(statusCode: 500, message: "not stubbed"))
    /// Popped in order — lets a test say "fail twice, then succeed".
    var confirmResults: [Result<CheckoutConfirmResponse, Error>] = []
    var statusResult: Result<BookingStatusSnapshot, Error> = .failure(
        CheckoutAPIError(statusCode: 404, message: "not stubbed"))

    private(set) var confirmCallCount = 0
    private(set) var lastConfirmBookingId: String?
    private(set) var statusCallCount = 0

    func submitBooking(_ request: BookingSubmitRequest) async throws -> BookingSubmitResponse {
        try submitResult.get()
    }

    func createPaymentIntent(bookingId: String, submissionKey: String, checkoutToken: String?,
                             amount: Double, customerEmail: String?, promoCode: String?,
                             priceVersion: String?) async throws -> CheckoutIntentResponse {
        try intentResult.get()
    }

    func confirmPayment(paymentIntentId: String, bookingId: String) async throws -> CheckoutConfirmResponse {
        confirmCallCount += 1
        lastConfirmBookingId = bookingId
        guard !confirmResults.isEmpty else {
            return CheckoutConfirmResponse(success: true, paymentStatus: "succeeded", jobStatus: "confirmed")
        }
        return try confirmResults.removeFirst().get()
    }

    func fetchBookingStatus(jobId: String) async throws -> BookingStatusSnapshot {
        statusCallCount += 1
        return try statusResult.get()
    }
}

// MARK: - Fixtures

private func makePending(stage: PendingBookingStage = .paid,
                         createdAt: Date = Date()) -> PendingBooking {
    PendingBooking(
        jobId: "job-abc-123",
        submissionKey: "11111111-2222-3333-4444-555555555555",
        checkoutToken: "ck_test",
        confirmationCode: "ABCD1234",
        paymentIntentId: "pi_test_123",
        amount: 149.00,
        stage: stage,
        createdAt: createdAt,
        cartFingerprint: "fp"
    )
}

// MARK: - Persistence

final class PendingBookingStoreTests: XCTestCase {

    private var defaults: UserDefaults!
    private var suiteName: String!

    override func setUp() {
        super.setUp()
        suiteName = "com.goumuve.umuve.tests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        super.tearDown()
    }

    func testPendingBookingSurvivesAStorageRoundTrip() {
        let store = PendingBookingStore(defaults: defaults)
        let record = makePending(stage: .intentCreated)

        store.save(record)

        // A *fresh* store instance — this is what a relaunched app sees.
        let reloaded = PendingBookingStore(defaults: defaults).load()
        XCTAssertEqual(reloaded, record, "The record must round-trip byte-for-byte")
        XCTAssertEqual(reloaded?.jobId, "job-abc-123")
        XCTAssertEqual(reloaded?.submissionKey, record.submissionKey,
                       "Reusing the submission key is what stops a retry double-charging")
        XCTAssertEqual(reloaded?.paymentIntentId, "pi_test_123")
        XCTAssertEqual(reloaded?.stage, .intentCreated)
    }

    func testClearRemovesTheRecord() {
        let store = PendingBookingStore(defaults: defaults)
        store.save(makePending())
        store.clear()
        XCTAssertNil(store.load())
    }

    func testUnpaidRecordGoesStaleButPaidOneNever() {
        let old = Date(timeIntervalSinceNow: -60 * 60 * 48)
        XCTAssertTrue(makePending(stage: .booked, createdAt: old).isStale())
        XCTAssertFalse(makePending(stage: .paid, createdAt: old).isStale(),
                       "A paid booking represents money and must never be dropped on age")
    }
}

// MARK: - Confirmation retry

@MainActor
final class CheckoutRecoveryServiceTests: XCTestCase {

    /// No real waiting — the backoff is injected.
    private func makeService(api: StubCheckoutAPI,
                             store: PendingBookingStoring) -> CheckoutRecoveryService {
        CheckoutRecoveryService(api: api, store: store, sleeper: { _ in })
    }

    func testConfirmIsRetriedOnTransientFailureAndThenSucceeds() async {
        let api = StubCheckoutAPI()
        // Two transport failures, then the server answers.
        api.confirmResults = [
            .failure(CheckoutAPIError(statusCode: 0, code: "network", message: "timed out")),
            .failure(CheckoutAPIError(statusCode: 503, message: "upstream down")),
            .success(CheckoutConfirmResponse(success: true, paymentStatus: "succeeded", jobStatus: "confirmed")),
        ]
        let store = InMemoryPendingBookingStore()
        let service = makeService(api: api, store: store)

        let result = await service.confirmPaidBooking(makePending(), maxAttempts: 5)

        guard case .success(let jobId) = result else {
            return XCTFail("A recoverable failure must not end the checkout: \(result)")
        }
        XCTAssertEqual(jobId, "job-abc-123")
        XCTAssertEqual(api.confirmCallCount, 3, "Should retry until the server answers")
        XCTAssertEqual(api.lastConfirmBookingId, "job-abc-123",
                       "Confirm must carry the job id so the server can adopt the intent")
        XCTAssertNil(store.load(), "The pending record is cleared only after confirm succeeds")
        XCTAssertEqual(service.state, .succeeded(jobId: "job-abc-123"))
    }

    func testConfirmStopsRetryingAClientErrorAndAsksForSupport() async {
        let api = StubCheckoutAPI()
        api.confirmResults = Array(
            repeating: .failure(CheckoutAPIError(statusCode: 400, message: "intent not succeeded")),
            count: 5
        )
        api.statusResult = .success(
            BookingStatusSnapshot(jobId: "job-abc-123", status: "pending", paymentStatus: "pending"))
        let store = InMemoryPendingBookingStore()
        let service = makeService(api: api, store: store)

        let result = await service.confirmPaidBooking(makePending(), maxAttempts: 5)

        guard case .failure = result else { return XCTFail("Expected a failure result") }
        XCTAssertEqual(api.confirmCallCount, 1, "A 400 is not retryable — retrying just burns time")
        XCTAssertNotNil(store.load(), "A paid-but-unconfirmed record must be kept for reconciliation")
        XCTAssertEqual(store.load()?.stage, .paid)
        guard case .needsSupport = service.state else {
            return XCTFail("Expected the support fallback, got \(service.state)")
        }
    }

    func testConfirmFallsBackToTheBookingReadWhenTheWebhookAlreadySettledIt() async {
        let api = StubCheckoutAPI()
        api.confirmResults = Array(
            repeating: .failure(CheckoutAPIError(statusCode: 404, message: "Payment not found")),
            count: 3
        )
        api.statusResult = .success(
            BookingStatusSnapshot(jobId: "job-abc-123", status: "confirmed", paymentStatus: "succeeded"))
        let store = InMemoryPendingBookingStore()
        let service = makeService(api: api, store: store)

        let result = await service.confirmPaidBooking(makePending(), maxAttempts: 3)

        guard case .success = result else {
            return XCTFail("The booking is settled server-side; that is a success: \(result)")
        }
        XCTAssertEqual(api.statusCallCount, 1)
        XCTAssertNil(store.load())
    }

    func testAlreadyPaidIsTreatedAsSuccessNotAnError() async {
        let api = StubCheckoutAPI()
        api.confirmResults = [
            .failure(CheckoutAPIError(statusCode: 409, code: "already_paid", message: "This booking is already paid")),
        ]
        let store = InMemoryPendingBookingStore()
        let service = makeService(api: api, store: store)

        let result = await service.confirmPaidBooking(makePending(), maxAttempts: 3)

        guard case .success = result else { return XCTFail("already_paid is a success for the customer") }
        XCTAssertEqual(api.confirmCallCount, 1)
        XCTAssertNil(store.load())
    }

    func testResumeReconcilesAPaidRecordOnLaunch() async {
        let api = StubCheckoutAPI()
        let store = InMemoryPendingBookingStore(seed: makePending(stage: .paid))
        let service = makeService(api: api, store: store)

        await service.resumeIfNeeded()

        XCTAssertEqual(api.confirmCallCount, 1, "A paid record must be confirmed, never re-charged")
        XCTAssertNil(store.load())
        XCTAssertEqual(service.state, .succeeded(jobId: "job-abc-123"))
    }

    func testResumeDropsAStaleUnpaidRecordWithoutCallingTheServer() async {
        let api = StubCheckoutAPI()
        let stale = makePending(stage: .booked, createdAt: Date(timeIntervalSinceNow: -60 * 60 * 48))
        let store = InMemoryPendingBookingStore(seed: stale)
        let service = makeService(api: api, store: store)

        await service.resumeIfNeeded()

        XCTAssertEqual(api.confirmCallCount, 0)
        XCTAssertEqual(api.statusCallCount, 0)
        XCTAssertNil(store.load())
    }
}

// MARK: - Request shape

@MainActor
final class BookingSubmitRequestTests: XCTestCase {

    func testRequestUsesTheFieldNamesTheBackendReads() throws {
        let request = BookingSubmitRequest(
            address: "123 Main St, Lake Worth, FL 33460",
            lat: 26.61,
            lng: -80.05,
            items: [BookingItemPayload(category: "furniture", quantity: 2, size: "medium")],
            photoURLs: ["https://cdn.example/1.jpg"],
            scheduledDate: "2026-09-12",
            scheduledTime: "08:00",
            estimatedPrice: 149.0,
            notes: "Side gate",
            promoCode: "SAVE10",
            priceVersion: nil
        )

        let body = request.jsonObject()

        // Address must be a STRING: the dict branch of create_booking()
        // collapses to `street` and drops city/zip.
        XCTAssertEqual(body["address"] as? String, "123 Main St, Lake Worth, FL 33460")
        XCTAssertEqual(body["lat"] as? Double, 26.61)
        XCTAssertEqual(body["lng"] as? Double, -80.05)
        XCTAssertEqual(body["scheduled_date"] as? String, "2026-09-12")
        XCTAssertEqual(body["scheduled_time"] as? String, "08:00")
        XCTAssertEqual(body["estimated_price"] as? Double, 149.0)
        XCTAssertEqual(body["promo_code"] as? String, "SAVE10")
        XCTAssertEqual(body["lead_source"] as? String, "ios_app")
        XCTAssertNil(body["price_version"], "Omitted while the backend doesn't emit one")

        let items = try XCTUnwrap(body["items"] as? [[String: Any]])
        XCTAssertEqual(items.first?["category"] as? String, "furniture")
        XCTAssertEqual(items.first?["quantity"] as? Int, 2)
        XCTAssertEqual(items.first?["size"] as? String, "medium")

        XCTAssertEqual((body["photos"] as? [String])?.count, 1,
                       "Photos go over as URLs under `photos`, which is what the model column stores")
    }

    func testBookingResponseReadsTheNestedJobAndCheckoutToken() throws {
        let json = Data("""
        {"success": true,
         "job": {"id": "job-1", "confirmation_code": "WXYZ0001", "total_price": 158.42},
         "payment": {"payment_status": "pending"},
         "checkout_token": "ck_abc"}
        """.utf8)

        let response = try JSONDecoder().decode(BookingSubmitResponse.self, from: json)

        XCTAssertEqual(response.jobId, "job-1")
        XCTAssertEqual(response.confirmationCode, "WXYZ0001")
        XCTAssertEqual(response.totalPrice, 158.42)
        XCTAssertEqual(response.checkoutToken, "ck_abc")
    }

    func testBookingStatusSnapshotDetectsSettlement() throws {
        let json = Data("""
        {"success": true,
         "booking": {"id": "job-1", "status": "confirmed", "total_price": 158.42,
                     "confirmation_code": "WXYZ0001",
                     "payment": {"payment_status": "succeeded", "amount": 158.42}}}
        """.utf8)

        let snapshot = try JSONDecoder().decode(BookingStatusSnapshot.self, from: json)

        XCTAssertTrue(snapshot.isSettled)
        XCTAssertFalse(snapshot.isDead)
        XCTAssertEqual(snapshot.paymentStatus, "succeeded")
    }

    func testSlotIdBecomesTheStartHour() {
        XCTAssertEqual(BookingReviewViewModel.apiTimeString(fromSlotId: "8-10"), "08:00")
        XCTAssertEqual(BookingReviewViewModel.apiTimeString(fromSlotId: "14-16"), "14:00")
        XCTAssertEqual(BookingReviewViewModel.apiTimeString(fromSlotId: "nonsense"), "09:00")
    }
}
