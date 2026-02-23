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
    let role: String

    enum CodingKeys: String, CodingKey {
        case identityToken = "identity_token"
        case nonce
        case userIdentifier
        case email
        case name
        case role
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

struct PhoneVerificationRequest: Codable {
    let phoneNumber: String
}

struct PhoneVerificationResponse: Codable {
    let success: Bool
    let message: String
    let code: String? // Only present in dev mode
}

struct PhoneVerifyCodeRequest: Codable {
    let phoneNumber: String
    let code: String
}

struct EmailSignupRequest: Codable {
    let email: String
    let password: String
    let name: String?
    let inviteCode: String?

    // Custom encoding to omit nil values (backend returns 500 when null is sent)
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(email, forKey: .email)
        try container.encode(password, forKey: .password)
        if let name = name {
            try container.encode(name, forKey: .name)
        }
        if let inviteCode = inviteCode {
            try container.encode(inviteCode, forKey: .inviteCode)
        }
    }

    enum CodingKeys: String, CodingKey {
        case email, password, name, inviteCode
    }
}

struct EmailLoginRequest: Codable {
    let email: String
    let password: String
}

struct PhoneLoginRequest: Codable {
    let phone: String
    let password: String
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
