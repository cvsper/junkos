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
            // Example: https://umuve-backend.onrender.com
            return "https://umuve-backend.onrender.com"
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
    
    private init() {
        // Check for environment override
        #if DEBUG
        environment = .development
        #else
        environment = .production
        #endif
    }
}
