//
//  APIClient.swift
//  Umuve
//
//  API client for backend communication
//

import Foundation
import UIKit

enum APIClientError: LocalizedError {
    case invalidURL
    case networkError(Error)
    case invalidResponse
    case serverError(String)
    case decodingError(Error)
    case unauthorized
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid API URL"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .invalidResponse:
            return "Invalid server response"
        case .serverError(let message):
            return message
        case .decodingError(let error):
            return "Data parsing error: \(error.localizedDescription)"
        case .unauthorized:
            return "Unauthorized access"
        }
    }
}

class APIClient {
    static let shared = APIClient()
    
    private let session: URLSession
    private let config = Config.shared
    
    private init() {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: configuration)
    }
    
    // MARK: - Private Helper Methods
    
    private func createRequest(
        endpoint: String,
        method: String = "GET",
        body: Data? = nil
    ) throws -> URLRequest {
        guard let url = URL(string: config.baseURL + endpoint) else {
            throw APIClientError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")

        // Automatically inject JWT auth header from Keychain
        if let token = KeychainHelper.loadString(forKey: "authToken") {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = body
        }

        return request
    }
    
    private func performRequest<T: Codable>(
        _ request: URLRequest,
        retryCount: Int = 0
    ) async throws -> T {
        do {
            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIClientError.invalidResponse
            }

            // Handle different status codes
            switch httpResponse.statusCode {
            case 200...299:
                // Success
                break
            case 401:
                // Try to refresh token and retry once
                if retryCount == 0 {
                    do {
                        try await refreshToken()
                        // Recreate request with new token
                        var newRequest = request
                        if let token = KeychainHelper.loadString(forKey: "authToken") {
                            newRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
                        }
                        return try await performRequest(newRequest, retryCount: 1)
                    } catch {
                        // Refresh failed, throw unauthorized
                        throw APIClientError.unauthorized
                    }
                }
                throw APIClientError.unauthorized
            case 400...499:
                // Client error - try to decode error message
                if let apiError = try? JSONDecoder().decode(APIError.self, from: data) {
                    throw APIClientError.serverError(apiError.error)
                }
                throw APIClientError.serverError("Client error: \(httpResponse.statusCode)")
            case 500...599:
                // Server error
                if let apiError = try? JSONDecoder().decode(APIError.self, from: data) {
                    throw APIClientError.serverError(apiError.error)
                }
                throw APIClientError.serverError("Server error: \(httpResponse.statusCode)")
            default:
                throw APIClientError.invalidResponse
            }

            // Decode response
            let decoder = JSONDecoder()
            do {
                return try decoder.decode(T.self, from: data)
            } catch {
                print("Decoding error: \(error)")
                print("Response data: \(String(data: data, encoding: .utf8) ?? "nil")")
                throw APIClientError.decodingError(error)
            }

        } catch let error as APIClientError {
            throw error
        } catch {
            throw APIClientError.networkError(error)
        }
    }
    
    // MARK: - Public API Methods
    
    /// Get all available services
    func getServices() async throws -> [APIService] {
        let request = try createRequest(endpoint: "/api/services")
        let response: ServicesResponse = try await performRequest(request)
        return response.services
    }
    
    /// Get price quote for selected services
    func getQuote(serviceIds: [String], zipCode: String) async throws -> QuoteResponse {
        let quoteRequest = QuoteRequest(services: serviceIds, zipCode: zipCode)
        let body = try JSONEncoder().encode(quoteRequest)
        
        let request = try createRequest(
            endpoint: "/api/quote",
            method: "POST",
            body: body
        )
        
        return try await performRequest(request)
    }
    
    /// Create a new booking
    func createBooking(
        address: Address,
        serviceIds: [String],
        photos: [Data],
        scheduledDateTime: String,
        customer: CustomerInfo,
        notes: String?,
        referralCode: String? = nil
    ) async throws -> BookingResponse {
        // Convert photos to base64
        let base64Photos = photos.map { $0.base64EncodedString() }

        // Format address
        let fullAddress = address.fullAddress

        // Only pass referral code if non-empty
        let code = referralCode?.trimmingCharacters(in: .whitespaces)
        let effectiveCode = (code?.isEmpty == false) ? code : nil

        let bookingRequest = BookingRequest(
            address: fullAddress,
            zipCode: address.zipCode,
            services: serviceIds,
            photos: base64Photos,
            scheduledDatetime: scheduledDateTime,
            notes: notes,
            customer: customer,
            referralCode: effectiveCode
        )

        let body = try JSONEncoder().encode(bookingRequest)

        let request = try createRequest(
            endpoint: "/api/bookings",
            method: "POST",
            body: body
        )

        return try await performRequest(request)
    }
    
    /// Get booking details by ID
    func getBooking(id: Int) async throws -> BookingResponse {
        let request = try createRequest(endpoint: "/api/bookings/\(id)")
        return try await performRequest(request)
    }
    
    /// Upload photos (multipart form data) - Alternative method for photo upload
    func uploadPhotos(_ photos: [Data]) async throws -> [String] {
        // Create multipart form data request
        let boundary = UUID().uuidString

        guard let url = URL(string: config.baseURL + "/api/upload/photos") else {
            throw APIClientError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")

        // Automatically inject JWT auth header from Keychain
        if let token = KeychainHelper.loadString(forKey: "authToken") {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()

        for (index, photoData) in photos.enumerated() {
            // Add boundary
            body.append("--\(boundary)\r\n".data(using: .utf8)!)

            // Add content disposition - field name "files" matches backend expectation
            body.append("Content-Disposition: form-data; name=\"files\"; filename=\"photo\(index).jpg\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)

            // Add photo data
            body.append(photoData)
            body.append("\r\n".data(using: .utf8)!)
        }

        // Add closing boundary
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        // Send request and decode response
        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIClientError.serverError("Photo upload failed: \(httpResponse.statusCode)")
        }

        // Decode response: { "success": true, "urls": [...] }
        struct UploadResponse: Codable {
            let success: Bool
            let urls: [String]
        }

        let uploadResponse = try JSONDecoder().decode(UploadResponse.self, from: data)
        return uploadResponse.urls
    }

    /// Create a new job/booking
    func createJob(
        serviceType: String,
        address: String,
        lat: Double,
        lng: Double,
        dropoffAddress: String?,
        dropoffLat: Double?,
        dropoffLng: Double?,
        photoUrls: [String],
        scheduledDate: String,
        scheduledTime: String,
        estimatedPrice: Double,
        volumeTier: String?,
        vehicleInfo: [String: String]?,
        distance: Double?
    ) async throws -> JobCreationResponse {
        var requestBody: [String: Any] = [
            "service_type": serviceType,
            "address": address,
            "lat": lat,
            "lng": lng,
            "photo_urls": photoUrls,
            "scheduled_date": scheduledDate,
            "scheduled_time": scheduledTime,
            "estimated_price": estimatedPrice
        ]

        // Add optional fields
        if let dropoffAddress = dropoffAddress {
            requestBody["dropoff_address"] = dropoffAddress
        }

        if let dropoffLat = dropoffLat {
            requestBody["dropoff_lat"] = dropoffLat
        }

        if let dropoffLng = dropoffLng {
            requestBody["dropoff_lng"] = dropoffLng
        }

        if let volumeTier = volumeTier {
            requestBody["volume_tier"] = volumeTier
        }

        if let vehicleInfo = vehicleInfo {
            requestBody["vehicle_info"] = vehicleInfo
        }

        if let distance = distance {
            requestBody["distance"] = distance
        }

        let body = try JSONSerialization.data(withJSONObject: requestBody)

        let request = try createRequest(
            endpoint: "/api/jobs",
            method: "POST",
            body: body
        )

        return try await performRequest(request)
    }
    
    /// Get customer's bookings
    func getCustomerBookings(email: String) async throws -> [BookingResponse] {
        let body = try JSONEncoder().encode(["email": email])
        let request = try createRequest(
            endpoint: "/api/bookings/customer",
            method: "POST",
            body: body
        )
        let response: BookingsListResponse = try await performRequest(request)
        return response.bookings
    }

    /// Get job/booking status by ID
    func getJobStatus(jobId: String) async throws -> JobStatusResponse {
        let request = try createRequest(endpoint: "/api/booking/\(jobId)")
        return try await performRequest(request)
    }

    /// Health check
    func healthCheck() async throws -> Bool {
        let request = try createRequest(endpoint: "/api/health")
        let response: [String: String] = try await performRequest(request)
        return response["status"] == "healthy"
    }

    /// Get pricing estimate
    func getPricingEstimate(
        serviceType: String,
        volumeTier: String?,
        vehicleInfo: [String: Any]?,
        pickupLat: Double?,
        pickupLng: Double?,
        dropoffLat: Double?,
        dropoffLng: Double?,
        scheduledDate: String?
    ) async throws -> PricingEstimate {
        var requestBody: [String: Any] = ["service_type": serviceType]

        // For Junk Removal: map volumeTier to items array approximation
        if serviceType == "Junk Removal", let tier = volumeTier {
            let quantity: Int
            switch tier {
            case "1/4 Truck": quantity = 2
            case "1/2 Truck": quantity = 5
            case "3/4 Truck": quantity = 10
            case "Full Truck": quantity = 16
            default: quantity = 5
            }

            requestBody["items"] = [["category": "general", "quantity": quantity, "size": "medium"]]
        }

        // For Auto Transport: include vehicle info
        if serviceType == "Auto Transport", let vehicle = vehicleInfo {
            requestBody["vehicle_info"] = vehicle
        }

        // Include address coordinates if available
        if let lat = pickupLat, let lng = pickupLng {
            requestBody["pickup_address"] = ["lat": lat, "lng": lng]
        }

        if let lat = dropoffLat, let lng = dropoffLng {
            requestBody["dropoff_address"] = ["lat": lat, "lng": lng]
        }

        // Include scheduled date if available
        if let date = scheduledDate {
            requestBody["scheduled_date"] = date
        }

        let body = try JSONSerialization.data(withJSONObject: requestBody)

        let request = try createRequest(
            endpoint: "/api/pricing/estimate",
            method: "POST",
            body: body
        )

        // Decode response with snake_case to camelCase conversion
        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }

        if httpResponse.statusCode != 200 {
            throw APIClientError.serverError("Pricing estimate failed: \(httpResponse.statusCode)")
        }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase

        // Decode the wrapper response
        struct EstimateResponse: Codable {
            let success: Bool
            let estimate: PricingEstimate
        }

        let estimateResponse = try decoder.decode(EstimateResponse.self, from: data)
        return estimateResponse.estimate
    }

    // MARK: - Referrals

    /// Get the current user's referral code
    func getReferralCode() async throws -> ReferralCodeResponse {
        let request = try createRequest(endpoint: "/api/referrals/my-code")
        return try await performRequest(request)
    }

    // MARK: - Authentication

    /// Validate existing auth token
    func validateToken() async throws -> User {
        let request = try createRequest(endpoint: "/api/auth/validate", method: "POST")
        let response: ValidateTokenResponse = try await performRequest(request)
        return response.user
    }

    /// Refresh auth token
    private func refreshToken() async throws {
        let request = try createRequest(endpoint: "/api/auth/refresh", method: "POST")
        let response: AuthRefreshResponse = try await performRequest(request)
        // Save new token to Keychain
        KeychainHelper.save(response.token, forKey: "authToken")
    }
}
