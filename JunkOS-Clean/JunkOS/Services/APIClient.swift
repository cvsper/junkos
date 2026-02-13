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
        
        if let body = body {
            request.httpBody = body
        }
        
        return request
    }
    
    private func performRequest<T: Codable>(
        _ request: URLRequest
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
        
        guard let url = URL(string: config.baseURL + "/api/photos") else {
            throw APIClientError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")
        
        var body = Data()
        
        for (index, photoData) in photos.enumerated() {
            // Add boundary
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            
            // Add content disposition
            body.append("Content-Disposition: form-data; name=\"photo_\(index)\"; filename=\"photo_\(index).jpg\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
            
            // Add photo data
            body.append(photoData)
            body.append("\r\n".data(using: .utf8)!)
        }
        
        // Add closing boundary
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = body
        
        // For now, return empty array as the backend endpoint doesn't exist yet
        // This is a placeholder for future photo upload endpoint
        return []
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

    /// Health check
    func healthCheck() async throws -> Bool {
        let request = try createRequest(endpoint: "/api/health")
        let response: [String: String] = try await performRequest(request)
        return response["status"] == "healthy"
    }

    // MARK: - Referrals

    /// Get the current user's referral code
    func getReferralCode() async throws -> ReferralCodeResponse {
        var request = try createRequest(endpoint: "/api/referrals/my-code")
        // Attach auth token
        if let authToken = UserDefaults.standard.string(forKey: "authToken") {
            request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        }
        return try await performRequest(request)
    }
}
