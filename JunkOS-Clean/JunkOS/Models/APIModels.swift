//
//  APIModels.swift
//  JunkOS
//
//  API request and response models
//

import Foundation

// MARK: - API Service
struct APIService: Codable, Identifiable {
    let id: String
    let name: String
    let description: String?
    let basePrice: Double
    let isPopular: Bool?
    
    enum CodingKeys: String, CodingKey {
        case id
        case name
        case description
        case basePrice = "base_price"
        case isPopular = "is_popular"
    }
    
    // Convert to local Service model
    func toService() -> Service {
        Service(
            id: id,
            name: name,
            icon: iconForService(name),
            price: "$\(Int(basePrice))",
            isPopular: isPopular ?? false
        )
    }
    
    private func iconForService(_ name: String) -> String {
        let lowercased = name.lowercased()
        if lowercased.contains("furniture") { return "sofa.fill" }
        if lowercased.contains("appliance") { return "refrigerator.fill" }
        if lowercased.contains("construction") || lowercased.contains("debris") { return "hammer.fill" }
        if lowercased.contains("electronic") { return "tv.fill" }
        if lowercased.contains("yard") || lowercased.contains("garden") { return "leaf.fill" }
        return "trash.fill"
    }
}

// MARK: - Services Response
struct ServicesResponse: Codable {
    let success: Bool
    let services: [APIService]
}

// MARK: - Quote Request
struct QuoteRequest: Codable {
    let services: [String]
    let zipCode: String
    
    enum CodingKeys: String, CodingKey {
        case services
        case zipCode = "zip_code"
    }
}

// MARK: - Quote Response
struct QuoteResponse: Codable {
    let success: Bool
    let estimatedPrice: Double
    let services: [APIService]
    let availableTimeSlots: [String]
    let currency: String
    
    enum CodingKeys: String, CodingKey {
        case success
        case estimatedPrice = "estimated_price"
        case services
        case availableTimeSlots = "available_time_slots"
        case currency
    }
}

// MARK: - Booking Request
struct BookingRequest: Codable {
    let address: String
    let zipCode: String
    let services: [String]
    let photos: [String]  // Base64 encoded images
    let scheduledDatetime: String
    let notes: String?
    let customer: CustomerInfo
    
    enum CodingKeys: String, CodingKey {
        case address
        case zipCode = "zip_code"
        case services
        case photos
        case scheduledDatetime = "scheduled_datetime"
        case notes
        case customer
    }
}

// MARK: - Customer Info
struct CustomerInfo: Codable {
    let name: String
    let email: String
    let phone: String
}

// MARK: - Booking Response
struct BookingResponse: Codable {
    let success: Bool
    let bookingId: Int
    let estimatedPrice: Double
    let confirmation: String
    let scheduledDatetime: String
    let services: [APIService]
    
    enum CodingKeys: String, CodingKey {
        case success
        case bookingId = "booking_id"
        case estimatedPrice = "estimated_price"
        case confirmation
        case scheduledDatetime = "scheduled_datetime"
        case services
    }
}

// MARK: - Bookings List Response
struct BookingsListResponse: Codable {
    let success: Bool
    let bookings: [BookingResponse]
}

// MARK: - Forgot Password
struct ForgotPasswordRequest: Codable {
    let email: String
}

struct ForgotPasswordResponse: Codable {
    let success: Bool
    let message: String?
}

// MARK: - API Error
struct APIError: Codable {
    let error: String
    let details: String?
}

// MARK: - Generic API Response
struct APIResponse<T: Codable>: Codable {
    let success: Bool
    let data: T?
    let error: String?
}
