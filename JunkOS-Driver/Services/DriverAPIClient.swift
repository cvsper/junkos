//
//  DriverAPIClient.swift
//  Umuve Pro
//
//  REST API client for all backend communication.
//  Uses async/await with URLSession. Attaches JWT from Keychain.
//

import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case network(Error)
    case invalidResponse
    case server(String)
    case decoding(Error)
    case unauthorized

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid API URL"
        case .network(let e): return "Network error: \(e.localizedDescription)"
        case .invalidResponse: return "Invalid server response"
        case .server(let msg): return msg
        case .decoding(let e): return "Parsing error: \(e.localizedDescription)"
        case .unauthorized: return "Session expired. Please log in again."
        }
    }
}

private struct ServerError: Codable {
    let error: String
}

actor DriverAPIClient {
    static let shared = DriverAPIClient()

    private let session: URLSession
    private let baseURL: String

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)
        self.baseURL = AppConfig.shared.baseURL
    }

    // MARK: - Core Request

    private func request<T: Decodable>(
        _ endpoint: String,
        method: String = "GET",
        body: (any Encodable)? = nil,
        authenticated: Bool = true
    ) async throws -> T {
        guard let url = URL(string: baseURL + endpoint) else {
            throw APIError.invalidURL
        }

        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if authenticated, let token = KeychainHelper.loadString(forKey: "authToken") {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body {
            req.httpBody = try JSONEncoder().encode(body)
        }

        let (data, response) = try await session.data(for: req)

        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        switch http.statusCode {
        case 200...299:
            break
        case 401:
            if let se = try? JSONDecoder().decode(ServerError.self, from: data) {
                throw APIError.server(se.error)
            }
            throw APIError.unauthorized
        case 400...499:
            if let se = try? JSONDecoder().decode(ServerError.self, from: data) {
                throw APIError.server(se.error)
            }
            throw APIError.server("Client error \(http.statusCode)")
        default:
            if let se = try? JSONDecoder().decode(ServerError.self, from: data) {
                throw APIError.server(se.error)
            }
            throw APIError.server("Server error \(http.statusCode)")
        }

        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    // MARK: - Auth

    func login(email: String, password: String) async throws -> AuthResponse {
        try await request("/api/auth/login", method: "POST",
                          body: LoginRequest(email: email, password: password),
                          authenticated: false)
    }

    func signup(email: String, password: String, name: String?) async throws -> AuthResponse {
        try await request("/api/auth/signup", method: "POST",
                          body: SignupRequest(email: email, password: password, name: name),
                          authenticated: false)
    }

    func appleSignIn(userIdentifier: String, email: String?, name: String?) async throws -> AuthResponse {
        try await request("/api/auth/apple", method: "POST",
                          body: AppleSignInRequest(userIdentifier: userIdentifier, email: email, name: name),
                          authenticated: false)
    }

    // MARK: - Contractor Registration

    func registerContractor(_ registration: RegistrationRequest) async throws -> RegistrationResponse {
        try await request("/api/drivers/register", method: "POST", body: registration)
    }

    func getContractorProfile() async throws -> ContractorProfileResponse {
        try await request("/api/drivers/profile")
    }

    // MARK: - Availability & Location

    func updateAvailability(isOnline: Bool) async throws -> AvailabilityResponse {
        try await request("/api/drivers/availability", method: "PUT",
                          body: AvailabilityRequest(isOnline: isOnline, availabilitySchedule: nil))
    }

    func updateLocation(lat: Double, lng: Double) async throws -> LocationUpdateResponse {
        try await request("/api/drivers/location", method: "PUT",
                          body: LocationUpdateRequest(lat: lat, lng: lng))
    }

    // MARK: - Jobs

    func getAvailableJobs(radius: Double = 30) async throws -> AvailableJobsResponse {
        try await request("/api/drivers/jobs/available?radius=\(radius)")
    }

    func acceptJob(jobId: String) async throws -> JobActionResponse {
        try await request("/api/drivers/jobs/\(jobId)/accept", method: "POST")
    }

    func declineJob(jobId: String) async throws -> JobActionResponse {
        try await request("/api/drivers/jobs/\(jobId)/decline", method: "POST")
    }

    func updateJobStatus(
        jobId: String,
        status: String,
        beforePhotos: [String]? = nil,
        afterPhotos: [String]? = nil
    ) async throws -> JobActionResponse {
        try await request(
            "/api/drivers/jobs/\(jobId)/status",
            method: "PUT",
            body: StatusUpdateRequest(
                status: status,
                beforePhotos: beforePhotos,
                afterPhotos: afterPhotos
            )
        )
    }

    // MARK: - Push Notifications

    func registerPushToken(_ token: String) async throws -> PushTokenResponse {
        try await request(
            "/api/push/register-token",
            method: "POST",
            body: PushTokenRequest(token: token, platform: "ios", appType: "driver")
        )
    }
}

// MARK: - Push Token Models

struct PushTokenRequest: Codable {
    let token: String
    let platform: String
    let appType: String

    enum CodingKeys: String, CodingKey {
        case token
        case platform
        case appType = "app_type"
    }
}

struct PushTokenResponse: Codable {
    let success: Bool
}
