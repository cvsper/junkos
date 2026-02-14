//
//  PaymentService.swift
//  Umuve
//
//  Payment service for creating payment intents and confirming payments
//  via the backend Stripe API. Includes Stripe Payment Sheet support.
//

import Foundation
import PassKit
import StripePaymentSheet

// MARK: - Payment Models

/// Response from POST /api/payments/create-intent-simple
/// The backend returns camelCase keys: clientSecret, paymentIntentId
struct PaymentIntentResponse: Codable {
    let clientSecret: String
    let paymentIntentId: String

    // The simple endpoint returns camelCase keys directly,
    // so no custom CodingKeys mapping needed.
}

/// Response from POST /api/payments/confirm-simple
struct PaymentConfirmResponse: Codable {
    let success: Bool
    let message: String?
}

/// Request body for creating a payment intent.
/// The backend expects: amount (float, in dollars), bookingId (string).
private struct CreateIntentRequest: Codable {
    let amount: Double       // Amount in dollars (e.g. 149.00)
    let bookingId: String?
    let customerEmail: String?
}

/// Request body for confirming a payment
private struct ConfirmPaymentRequest: Codable {
    let paymentIntentId: String
    let paymentMethodType: String
}

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

    /// Track current PaymentIntent ID for confirmation
    var paymentIntentId: String?

    private init() {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: configuration)
    }

    // MARK: - Stripe Configuration

    /// Configure Stripe SDK with publishable key. Call once at app startup or lazily on first use.
    static func configureStripe() {
        STPAPIClient.shared.publishableKey = Config.shared.stripePublishableKey
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

    // MARK: - Payment Sheet Preparation

    /// Prepares a Stripe Payment Sheet for customer payment.
    /// Creates a PaymentIntent via backend and returns a configured PaymentSheet.
    /// - Parameters:
    ///   - amountInDollars: The total amount to charge in dollars
    ///   - bookingDescription: Optional description for the payment
    /// - Returns: Configured PaymentSheet ready for presentation
    @MainActor
    func preparePaymentSheet(
        amountInDollars: Double,
        bookingDescription: String = "Umuve Booking"
    ) async throws -> PaymentSheet {
        // Ensure Stripe is configured
        PaymentService.configureStripe()

        // Create PaymentIntent via backend
        let response = try await createPaymentIntent(
            amountInDollars: amountInDollars,
            bookingId: nil,
            customerEmail: nil
        )

        // Store the intent ID for later confirmation
        self.paymentIntentId = response.paymentIntentId

        // Configure Payment Sheet
        var configuration = PaymentSheet.Configuration()
        configuration.merchantDisplayName = "Umuve"
        configuration.applePay = .init(
            merchantId: "merchant.com.goumuve.app",
            merchantCountryCode: "US"
        )
        configuration.returnURL = "umuve://payment-return"
        configuration.allowsDelayedPaymentMethods = false

        // Create and return Payment Sheet
        return PaymentSheet(
            paymentIntentClientSecret: response.clientSecret,
            configuration: configuration
        )
    }

    // MARK: - Create Payment Intent

    /// Creates a PaymentIntent on the backend and returns the client secret.
    /// Uses the `/api/payments/create-intent-simple` endpoint.
    /// - Parameters:
    ///   - amountInDollars: The total amount to charge in dollars (e.g., 149.00)
    ///   - bookingId: Optional booking ID to associate with the payment
    ///   - customerEmail: Optional customer email for the receipt
    /// - Returns: PaymentIntentResponse containing clientSecret and paymentIntentId
    @MainActor
    func createPaymentIntent(
        amountInDollars: Double,
        bookingId: String? = nil,
        customerEmail: String? = nil
    ) async throws -> PaymentIntentResponse {
        isProcessing = true
        lastError = nil

        defer { isProcessing = false }

        let requestBody = CreateIntentRequest(
            amount: amountInDollars,
            bookingId: bookingId,
            customerEmail: customerEmail
        )

        let body = try JSONEncoder().encode(requestBody)

        guard let url = URL(string: config.baseURL + "/api/payments/create-intent-simple") else {
            let error = PaymentError.invalidURL
            lastError = error
            throw error
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")
        if let authToken = KeychainHelper.loadString(forKey: "authToken") {
            request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = body

        do {
            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                let error = PaymentError.invalidResponse
                lastError = error
                throw error
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                let message: String
                if let apiError = try? JSONDecoder().decode(APIError.self, from: data) {
                    message = apiError.error
                } else {
                    message = "Server error: \(httpResponse.statusCode)"
                }
                let error = PaymentError.serverError(message)
                lastError = error
                throw error
            }

            let decoder = JSONDecoder()
            do {
                return try decoder.decode(PaymentIntentResponse.self, from: data)
            } catch {
                let paymentError = PaymentError.decodingError(error)
                lastError = paymentError
                throw paymentError
            }

        } catch let error as PaymentError {
            throw error
        } catch {
            let paymentError = PaymentError.networkError(error)
            lastError = paymentError
            throw paymentError
        }
    }

    // MARK: - Confirm Payment

    /// Confirms a payment on the backend after client-side authorization.
    /// Uses the `/api/payments/confirm-simple` endpoint (requires JWT auth).
    /// - Parameters:
    ///   - paymentIntentId: The ID of the PaymentIntent to confirm
    ///   - paymentMethodType: The method used (e.g., "apple_pay" or "card")
    /// - Returns: PaymentConfirmResponse indicating success
    @MainActor
    func confirmPayment(
        paymentIntentId: String,
        paymentMethodType: String = "card"
    ) async throws -> PaymentConfirmResponse {
        isProcessing = true
        lastError = nil

        defer { isProcessing = false }

        let requestBody = ConfirmPaymentRequest(
            paymentIntentId: paymentIntentId,
            paymentMethodType: paymentMethodType
        )

        let body = try JSONEncoder().encode(requestBody)

        guard let url = URL(string: config.baseURL + "/api/payments/confirm-simple") else {
            let error = PaymentError.invalidURL
            lastError = error
            throw error
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")
        if let authToken = KeychainHelper.loadString(forKey: "authToken") {
            request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = body

        do {
            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                let error = PaymentError.invalidResponse
                lastError = error
                throw error
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                let message: String
                if let apiError = try? JSONDecoder().decode(APIError.self, from: data) {
                    message = apiError.error
                } else {
                    message = "Payment confirmation failed: \(httpResponse.statusCode)"
                }
                let error = PaymentError.serverError(message)
                lastError = error
                throw error
            }

            let decoder = JSONDecoder()
            do {
                return try decoder.decode(PaymentConfirmResponse.self, from: data)
            } catch {
                let paymentError = PaymentError.decodingError(error)
                lastError = paymentError
                throw paymentError
            }

        } catch let error as PaymentError {
            throw error
        } catch {
            let paymentError = PaymentError.networkError(error)
            lastError = paymentError
            throw paymentError
        }
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
