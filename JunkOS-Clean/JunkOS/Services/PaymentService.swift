//
//  PaymentService.swift
//  JunkOS
//
//  Payment service for creating payment intents and confirming payments
//  via the backend Stripe API. Does NOT use the Stripe SDK directly.
//

import Foundation
import PassKit

// MARK: - Payment Models

/// Response from POST /api/payments/create-intent
struct PaymentIntentResponse: Codable {
    let clientSecret: String
    let paymentIntentId: String

    enum CodingKeys: String, CodingKey {
        case clientSecret = "client_secret"
        case paymentIntentId = "payment_intent_id"
    }
}

/// Response from POST /api/payments/confirm
struct PaymentConfirmResponse: Codable {
    let success: Bool
    let message: String?
}

/// Request body for creating a payment intent
private struct CreateIntentRequest: Codable {
    let amount: Int          // Amount in cents
    let currency: String
    let bookingId: Int?
    let customerEmail: String?

    enum CodingKeys: String, CodingKey {
        case amount
        case currency
        case bookingId = "booking_id"
        case customerEmail = "customer_email"
    }
}

/// Request body for confirming a payment
private struct ConfirmPaymentRequest: Codable {
    let paymentIntentId: String
    let paymentMethodType: String

    enum CodingKeys: String, CodingKey {
        case paymentIntentId = "payment_intent_id"
        case paymentMethodType = "payment_method_type"
    }
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

    private init() {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: configuration)
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

    // MARK: - Create Payment Intent

    /// Creates a PaymentIntent on the backend and returns the client secret
    /// - Parameters:
    ///   - amountInDollars: The total amount to charge in dollars (e.g., 149.00)
    ///   - bookingId: Optional booking ID to associate with the payment
    ///   - customerEmail: Optional customer email for the receipt
    /// - Returns: PaymentIntentResponse containing clientSecret and paymentIntentId
    @MainActor
    func createPaymentIntent(
        amountInDollars: Double,
        bookingId: Int? = nil,
        customerEmail: String? = nil
    ) async throws -> PaymentIntentResponse {
        isProcessing = true
        lastError = nil

        defer { isProcessing = false }

        let amountInCents = Int(amountInDollars * 100)

        let requestBody = CreateIntentRequest(
            amount: amountInCents,
            currency: "usd",
            bookingId: bookingId,
            customerEmail: customerEmail
        )

        let body = try JSONEncoder().encode(requestBody)

        guard let url = URL(string: config.baseURL + "/api/payments/create-intent") else {
            let error = PaymentError.invalidURL
            lastError = error
            throw error
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")
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

    /// Confirms a payment on the backend after client-side authorization
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

        guard let url = URL(string: config.baseURL + "/api/payments/confirm") else {
            let error = PaymentError.invalidURL
            lastError = error
            throw error
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")
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
    ///   - label: Description shown on the payment sheet (e.g., "JunkOS Pickup")
    /// - Returns: A configured PKPaymentRequest
    func createApplePayRequest(amount: Double, label: String = "JunkOS Pickup") -> PKPaymentRequest {
        let request = PKPaymentRequest()
        request.merchantIdentifier = "merchant.com.junkos.app"
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
