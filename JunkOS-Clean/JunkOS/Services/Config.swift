//
//  Config.swift
//  Umuve
//
//  Environment configuration for API access
//

import Foundation

enum APIEnvironment {
    case development
    case production

    var baseURL: String {
        switch self {
        case .development:
            return "http://localhost:8080"
        case .production:
            // TODO: Replace with your actual Render URL after deployment
            // Example: https://junkos-backend.onrender.com
            return "https://junkos-backend.onrender.com"
        }
    }

    var socketURL: String {
        switch self {
        case .development:
            return "http://localhost:8080"
        case .production:
            return "https://junkos-backend.onrender.com"
        }
    }

    var apiKey: String {
        // In production, this should come from a secure source (keychain, env config, etc.)
        switch self {
        case .development:
            return "umuve-api-key-12345"
        case .production:
            return "umuve-api-key-12345"  // Should be different in production
        }
    }

    /// Stripe publishable key.
    ///
    /// Looked up in this order so the real key never has to live in source
    /// control:
    ///   1. `StripePublishableKey` in Info.plist (recommended — set per
    ///      build configuration via an xcconfig file or Build Settings →
    ///      User-Defined → STRIPE_PUBLISHABLE_KEY).
    ///   2. Hardcoded placeholder (only for new clones that haven't been
    ///      provisioned yet). PaymentService.configureStripe() prints a
    ///      runtime warning when the placeholder is used so the
    ///      misconfiguration is visible in the Xcode console.
    var stripePublishableKey: String {
        if let key = Bundle.main.object(forInfoDictionaryKey: "StripePublishableKey") as? String,
           !key.isEmpty,
           !key.contains("PLACEHOLDER") {
            return key
        }

        switch self {
        case .development:
            return "pk_test_PLACEHOLDER"
        case .production:
            return "pk_live_PLACEHOLDER"
        }
    }
}

class Config {
    static let shared = Config()

    // Default to development for now
    var environment: APIEnvironment = .development

    var baseURL: String {
        environment.baseURL
    }

    var apiKey: String {
        environment.apiKey
    }

    var stripePublishableKey: String {
        environment.stripePublishableKey
    }

    var socketURL: String {
        environment.socketURL
    }

    private init() {
        // Check for environment override
        #if DEBUG
        environment = .development
        #else
        environment = .production
        #endif
    }
}
