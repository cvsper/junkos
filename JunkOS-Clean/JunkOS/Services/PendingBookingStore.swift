//
//  PendingBookingStore.swift
//  Umuve
//
//  Durable record of a checkout that has started on the server but has not
//  been confirmed yet (audit F05).
//
//  The old flow charged the card first and only then tried to create a job,
//  so a crash, a backgrounded app, or a dropped response between the charge
//  and the follow-up call left a paid customer with no booking and no way to
//  recover. The record below is written BEFORE money can move and updated at
//  every step, so relaunching the app can always answer "what happened to my
//  payment?" without asking the customer to pay again.
//
//  Stored in UserDefaults rather than the Keychain on purpose: it holds no
//  secret (a job UUID, a submission key, and a booking-scoped checkout token
//  that the server binds to that one job), and it must survive app death
//  without a Keychain prompt.
//

import Foundation

// MARK: - Stage

/// How far a checkout got. The recovery path branches on this, so the order
/// matters: `.paid` means Stripe told us the charge succeeded and we must
/// never re-charge from that state — only re-confirm.
enum PendingBookingStage: String, Codable {
    /// The Job exists on the server. No PaymentIntent yet. Safe to abandon.
    case booked
    /// A PaymentIntent exists for this booking. The Stripe sheet is up or was
    /// dismissed. Safe to retry — the same submission key returns the same
    /// intent instead of minting a second payable one.
    case intentCreated
    /// Stripe reported `.completed`. Money has (very probably) moved. From
    /// here the only correct action is to keep confirming until the server
    /// agrees, or hand the customer a job number for support.
    case paid
}

// MARK: - Record

struct PendingBooking: Codable, Equatable {
    /// Server Job UUID — the thing support needs if anything goes wrong.
    let jobId: String
    /// One uuid per payment attempt series. Sent on every create-intent call
    /// so a retry returns the SAME PaymentIntent (backend audit F06).
    var submissionKey: String
    /// Booking-scoped capability from POST /api/booking. Lets a guest (or a
    /// session whose token expired) pay for exactly this booking.
    var checkoutToken: String?
    var confirmationCode: String?
    var paymentIntentId: String?
    /// Server-computed total at the time the attempt was created.
    var amount: Double
    var stage: PendingBookingStage
    var createdAt: Date
    /// Identifies the cart this booking was created from. A record whose
    /// fingerprint no longer matches the wizard is not reused — we would be
    /// charging for a different job than the one on screen.
    var cartFingerprint: String

    var isPaid: Bool { stage == .paid }

    /// An unpaid record eventually stops being worth resuming. A paid one
    /// never expires — it represents money and must be reconciled.
    func isStale(now: Date = Date(), maxAge: TimeInterval = 24 * 60 * 60) -> Bool {
        guard stage != .paid else { return false }
        return now.timeIntervalSince(createdAt) > maxAge
    }
}

// MARK: - Storage

protocol PendingBookingStoring: AnyObject {
    func load() -> PendingBooking?
    func save(_ booking: PendingBooking)
    func clear()
}

final class PendingBookingStore: PendingBookingStoring {
    /// Key is spelled out in the audit remediation; don't rename without a
    /// migration or in-flight bookings become unrecoverable on upgrade.
    static let storageKey = "pending_booking"

    static let shared = PendingBookingStore()

    private let defaults: UserDefaults
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        // Seconds-since-epoch, not ISO8601: ISO8601 truncates to whole
        // seconds, so a record did not survive a save/load round trip
        // unchanged. Equality on the record is how the resume path decides
        // whether it is looking at the same attempt.
        encoder.dateEncodingStrategy = .secondsSince1970
        decoder.dateDecodingStrategy = .secondsSince1970
    }

    func load() -> PendingBooking? {
        guard let data = defaults.data(forKey: Self.storageKey) else { return nil }
        return try? decoder.decode(PendingBooking.self, from: data)
    }

    func save(_ booking: PendingBooking) {
        guard let data = try? encoder.encode(booking) else { return }
        defaults.set(data, forKey: Self.storageKey)
    }

    func clear() {
        defaults.removeObject(forKey: Self.storageKey)
    }
}
