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
            // Attempt silent token refresh on 401
            if authenticated {
                do {
                    let refreshResponse: AuthRefreshResponse = try await refreshToken()
                    if refreshResponse.success {
                        KeychainHelper.save(refreshResponse.token, forKey: "authToken")
                        // Retry original request once with new token
                        return try await request(endpoint, method: method, body: body, authenticated: authenticated)
                    }
                } catch {
                    // Refresh failed, throw unauthorized
                }
            }
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

    func appleSignIn(
        identityToken: String,
        nonce: String?,
        userIdentifier: String,
        email: String?,
        name: String?
    ) async throws -> AuthResponse {
        try await request(
            "/api/auth/apple",
            method: "POST",
            body: AppleSignInRequest(
                identityToken: identityToken,
                nonce: nonce,
                userIdentifier: userIdentifier,
                email: email,
                name: name
            ),
            authenticated: false
        )
    }

    func refreshToken() async throws -> AuthRefreshResponse {
        try await request("/api/auth/refresh", method: "POST", authenticated: true)
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

    // MARK: - Stripe Connect

    func createConnectAccount() async throws -> ConnectAccountResponse {
        try await request("/api/payments/connect/create-account", method: "POST")
    }

    func createAccountLink() async throws -> ConnectAccountLinkResponse {
        try await request("/api/payments/connect/account-link", method: "POST")
    }

    func getConnectStatus() async throws -> ConnectStatusResponse {
        try await request("/api/payments/connect/status")
    }

    // MARK: - Payments & Earnings

    func getEarningsHistory() async throws -> EarningsHistoryResponse {
        try await request("/api/payments/earnings/history")
    }

    // MARK: - Volume Adjustment

    func proposeVolumeAdjustment(jobId: String, actualVolume: Double) async throws -> VolumeProposalResponse {
        struct Body: Encodable {
            let actual_volume: Double
        }
        return try await request(
            "/api/drivers/jobs/\(jobId)/volume",
            method: "POST",
            body: Body(actual_volume: actualVolume)
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

// MARK: - Stripe Connect Models

struct ConnectAccountResponse: Codable {
    let success: Bool
    let accountId: String?
    enum CodingKeys: String, CodingKey {
        case success
        case accountId = "account_id"
    }
}

struct ConnectAccountLinkResponse: Codable {
    let success: Bool
    let url: String
    let expiresAt: Int?
    enum CodingKeys: String, CodingKey {
        case success
        case url
        case expiresAt = "expires_at"
    }
}

struct ConnectStatusResponse: Codable {
    let success: Bool
    let status: String
    let chargesEnabled: Bool
    let payoutsEnabled: Bool
    let detailsSubmitted: Bool?
    enum CodingKeys: String, CodingKey {
        case success
        case status
        case chargesEnabled = "charges_enabled"
        case payoutsEnabled = "payouts_enabled"
        case detailsSubmitted = "details_submitted"
    }
}

// MARK: - Earnings Models

struct EarningsHistoryResponse: Codable {
    let success: Bool
    let entries: [EarningsEntryResponse]
    let summary: EarningsSummaryResponse

    struct EarningsEntryResponse: Codable {
        let id: String
        let jobId: String
        let address: String
        let amount: Double      // driver_payout_amount (80% take)
        let date: String?       // ISO 8601 date string
        let payoutStatus: String // "pending", "processing", "paid"

        enum CodingKeys: String, CodingKey {
            case id
            case jobId = "job_id"
            case address
            case amount
            case date
            case payoutStatus = "payout_status"
        }
    }

    struct EarningsSummaryResponse: Codable {
        let today: Double
        let week: Double
        let month: Double
        let allTime: Double

        enum CodingKeys: String, CodingKey {
            case today
            case week
            case month
            case allTime = "all_time"
        }
    }
}
