//
//  PaymentService.swift
//  Umuve
//
//  Stripe SDK glue: publishable-key configuration, Apple Pay availability,
//  and building a PaymentSheet from a client secret the backend issued.
//
//  Deliberately does NO networking — see the note below (audit F05).
//

import Foundation
import PassKit
import StripePaymentSheet

// MARK: - Payment Models

// NOTE (audit F05): the PaymentIntent / confirm request models and their
// networking used to live here, and `preparePaymentSheet` created an intent
// with `bookingId: nil` — a charge against no booking, which /confirm could
// then never match. Both calls now live in APIClient's BookingCheckoutAPI
// conformance and always carry a job id plus a submission key. This service
// is Stripe-SDK-only: configuration, Apple Pay availability, and turning a
// client secret the server already issued into a PaymentSheet.

// MARK: - Payment Error

enum PaymentError: LocalizedError {
    case invalidURL
    case networkError(Error)
    case invalidResponse
    case serverError(String)
    case decodingError(Error)
    case applePayNotAvailable
    case applePayCancelled
    case applePayFailed(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid payment URL"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .invalidResponse:
            return "Invalid server response"
        case .serverError(let message):
            return message
        case .decodingError(let error):
            return "Data parsing error: \(error.localizedDescription)"
        case .applePayNotAvailable:
            return "Apple Pay is not available on this device"
        case .applePayCancelled:
            return "Apple Pay was cancelled"
        case .applePayFailed(let reason):
            return "Apple Pay failed: \(reason)"
        }
    }
}

// MARK: - Payment Service

class PaymentService: ObservableObject {
    static let shared = PaymentService()

    @Published var isProcessing = false
    @Published var lastError: PaymentError?

    private let session: URLSession
    private let config = Config.shared

    private init() {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: configuration)
    }

    // MARK: - Stripe Configuration

    /// Configure Stripe SDK with publishable key. Call once at app startup or lazily on first use.
    static func configureStripe() {
        let key = Config.shared.stripePublishableKey
        STPAPIClient.shared.publishableKey = key

        // Loud, unmissable runtime warning when the placeholder key is in
        // use — Stripe will reject every PaymentIntent + Payment Sheet
        // attempt with this value, so debugging the symptom ("payment
        // failed" with no clear reason) tends to lead here. Set the
        // `StripePublishableKey` Info.plist value to your real
        // pk_live_… / pk_test_… key to silence this.
        if key.contains("PLACEHOLDER") {
            print("""
            ⚠️ ⚠️ ⚠️ STRIPE NOT CONFIGURED ⚠️ ⚠️ ⚠️
            Config.shared.stripePublishableKey = "\(key)"
            All payment attempts will fail until this is replaced with a
            real Stripe publishable key. Set `StripePublishableKey` in
            Info.plist (recommended) or edit Config.swift directly.
            """)
        }
    }

    // MARK: - Apple Pay Availability

    /// Check if Apple Pay is available on this device.
    /// Uses the base `canMakePayments()` check so the button appears
    /// even when no cards are added yet (iOS will prompt to add one).
    var isApplePayAvailable: Bool {
        PKPaymentAuthorizationViewController.canMakePayments()
    }

    /// Supported Apple Pay payment networks
    var supportedPaymentNetworks: [PKPaymentNetwork] {
        [.visa, .masterCard, .amex, .discover]
    }

    // MARK: - Payment Sheet

    /// Build a Payment Sheet for a client secret the SERVER already issued
    /// against a real booking (see `APIClient.createPaymentIntent`).
    ///
    /// This does no networking on purpose. The old
    /// `preparePaymentSheet(amountInDollars:)` created its own intent with no
    /// booking id, which is exactly how a card could be charged with no job
    /// to attach the payment to (audit F05).
    @MainActor
    func makePaymentSheet(clientSecret: String) -> PaymentSheet {
        PaymentService.configureStripe()

        var configuration = PaymentSheet.Configuration()
        configuration.merchantDisplayName = "Umuve"
        configuration.applePay = .init(
            merchantId: "merchant.com.goumuve.app",
            merchantCountryCode: "US"
        )
        configuration.returnURL = "umuve://payment-return"
        configuration.allowsDelayedPaymentMethods = false

        return PaymentSheet(
            paymentIntentClientSecret: clientSecret,
            configuration: configuration
        )
    }

    // MARK: - Apple Pay Payment Request

    /// Creates a PKPaymentRequest for Apple Pay authorization
    /// - Parameters:
    ///   - amount: The total amount in dollars
    ///   - label: Description shown on the payment sheet (e.g., "Umuve Pickup")
    /// - Returns: A configured PKPaymentRequest
    func createApplePayRequest(amount: Double, label: String = "Umuve Pickup") -> PKPaymentRequest {
        let request = PKPaymentRequest()
        request.merchantIdentifier = "merchant.com.goumuve.app"
        request.supportedNetworks = supportedPaymentNetworks
        request.merchantCapabilities = .capability3DS
        request.countryCode = "US"
        request.currencyCode = "USD"
        request.paymentSummaryItems = [
            PKPaymentSummaryItem(label: label, amount: NSDecimalNumber(value: amount))
        ]
        return request
    }
}
