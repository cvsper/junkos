//
//  AuthModels.swift
//  Umuve Pro
//
//  Authentication-related data models matching backend API contracts.
//

import Foundation

// MARK: - Request Models

struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct SignupRequest: Codable {
    let email: String
    let password: String
    let name: String?
}

struct AppleSignInRequest: Codable {
    let userIdentifier: String
    let email: String?
    let name: String?
}

// MARK: - Response Models

struct AuthResponse: Codable {
    let success: Bool
    let token: String
    let user: DriverUser
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
