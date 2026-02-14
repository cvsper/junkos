//
//  AuthModels.swift
//  Umuve Pro
//
//  Authentication-related data models matching backend API contracts.
//

import Foundation

// MARK: - Request Models

struct AppleSignInRequest: Codable {
    let identityToken: String?
    let nonce: String?
    let userIdentifier: String
    let email: String?
    let name: String?

    enum CodingKeys: String, CodingKey {
        case identityToken = "identity_token"
        case nonce
        case userIdentifier
        case email
        case name
    }
}

// MARK: - Response Models

struct AuthResponse: Codable {
    let success: Bool
    let token: String
    let user: DriverUser
}

struct AuthRefreshResponse: Codable {
    let success: Bool
    let token: String
}

struct DriverUser: Codable, Identifiable {
    let id: String
    let name: String?
    let email: String?
    let phoneNumber: String?
    let role: String?

    var displayName: String {
        name ?? email ?? "Driver"
    }

    var initials: String {
        guard let name = name, !name.isEmpty else { return "D" }
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return String(parts[0].prefix(1) + parts[1].prefix(1)).uppercased()
        }
        return String(name.prefix(1)).uppercased()
    }
}
