//
//  Config.swift
//  Umuve Pro
//
//  Environment configuration for API access.
//  Shares the same backend as the customer app.
//

import Foundation

enum APIEnvironment {
    case development
    case production

    var baseURL: String {
        switch self {
        case .development:
            return "https://junkos-backend.onrender.com" // Use production in DEBUG for testing
        case .production:
            return "https://junkos-backend.onrender.com"
        }
    }

    var socketURL: String {
        switch self {
        case .development:
            return "https://junkos-backend.onrender.com" // Use production in DEBUG for testing
        case .production:
            return "https://junkos-backend.onrender.com"
        }
    }
}

final class AppConfig {
    static let shared = AppConfig()

    var environment: APIEnvironment

    var baseURL: String { environment.baseURL }
    var socketURL: String { environment.socketURL }

    private init() {
        #if DEBUG
        environment = .development
        #else
        environment = .production
        #endif
    }
}
