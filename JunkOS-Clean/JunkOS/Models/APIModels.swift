//
//  APIModels.swift
//  Umuve
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
    let referralCode: String?

    enum CodingKeys: String, CodingKey {
        case address
        case zipCode = "zip_code"
        case services
        case photos
        case scheduledDatetime = "scheduled_datetime"
        case notes
        case customer
        case referralCode = "referral_code"
    }
}

// MARK: - Customer Info
struct CustomerInfo: Codable {
    let name: String
    let email: String
    let phone: String
}

// MARK: - Booking Response
// Handles both legacy booking creation responses and Job-based customer booking lists.
struct BookingResponse: Codable {
    // Core identification — legacy uses booking_id (Int), Job model uses id (String)
    let bookingId: String
    let confirmation: String

    // Pricing
    let estimatedPrice: Double

    // Schedule
    let scheduledDatetime: String

    // Status
    let status: String?

    // Services (only present in legacy creation response)
    let services: [APIService]

    // Operator delegation fields
    let operatorId: String?
    let operatorName: String?
    let delegatedAt: String?

    // Driver assignment
    let driverId: String?
    let driverName: String?

    // Volume adjustment
    let volumeAdjustmentProposed: Bool?
    let adjustedPrice: Double?
    let adjustedVolume: Double?

    // Tracking
    let address: String?

    enum CodingKeys: String, CodingKey {
        // Legacy creation response keys
        case bookingId = "booking_id"
        case estimatedPrice = "estimated_price"
        case scheduledDatetime = "scheduled_datetime"
        case services
        case confirmation
        case success
        // Job model keys
        case id
        case totalPrice = "total_price"
        case scheduledAt = "scheduled_at"
        case status
        // Operator fields
        case operatorId = "operator_id"
        case operatorName = "operator_name"
        case delegatedAt = "delegated_at"
        // Driver
        case driverId = "driver_id"
        case driverName = "driver_name"
        // Volume adjustment
        case volumeAdjustmentProposed = "volume_adjustment_proposed"
        case adjustedPrice = "adjusted_price"
        case adjustedVolume = "adjusted_volume"
        // Tracking
        case address
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // bookingId: try legacy "booking_id" (Int -> String), then Job "id" (String)
        if let legacyId = try? container.decode(Int.self, forKey: .bookingId) {
            bookingId = String(legacyId)
        } else if let jobId = try? container.decode(String.self, forKey: .id) {
            bookingId = jobId
        } else {
            bookingId = "unknown"
        }

        // estimatedPrice: try "estimated_price", then "total_price"
        if let ep = try? container.decode(Double.self, forKey: .estimatedPrice) {
            estimatedPrice = ep
        } else if let tp = try? container.decode(Double.self, forKey: .totalPrice) {
            estimatedPrice = tp
        } else {
            estimatedPrice = 0.0
        }

        // scheduledDatetime: try "scheduled_datetime", then "scheduled_at"
        if let sd = try? container.decode(String.self, forKey: .scheduledDatetime) {
            scheduledDatetime = sd
        } else if let sa = try? container.decode(String.self, forKey: .scheduledAt) {
            scheduledDatetime = sa
        } else {
            scheduledDatetime = ""
        }

        confirmation = (try? container.decode(String.self, forKey: .confirmation)) ?? "Confirmed"
        services = (try? container.decode([APIService].self, forKey: .services)) ?? []
        status = try? container.decode(String.self, forKey: .status)

        // Operator fields
        operatorId = try? container.decode(String.self, forKey: .operatorId)
        operatorName = try? container.decode(String.self, forKey: .operatorName)
        delegatedAt = try? container.decode(String.self, forKey: .delegatedAt)

        // Driver
        driverId = try? container.decode(String.self, forKey: .driverId)
        driverName = try? container.decode(String.self, forKey: .driverName)

        // Volume adjustment
        volumeAdjustmentProposed = try? container.decode(Bool.self, forKey: .volumeAdjustmentProposed)
        adjustedPrice = try? container.decode(Double.self, forKey: .adjustedPrice)
        adjustedVolume = try? container.decode(Double.self, forKey: .adjustedVolume)

        // Tracking
        address = try? container.decode(String.self, forKey: .address)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(bookingId, forKey: .id)
        try container.encode(estimatedPrice, forKey: .estimatedPrice)
        try container.encode(scheduledDatetime, forKey: .scheduledDatetime)
        try container.encode(confirmation, forKey: .confirmation)
        try container.encode(services, forKey: .services)
        try container.encodeIfPresent(status, forKey: .status)
        try container.encodeIfPresent(operatorId, forKey: .operatorId)
        try container.encodeIfPresent(operatorName, forKey: .operatorName)
        try container.encodeIfPresent(delegatedAt, forKey: .delegatedAt)
        try container.encodeIfPresent(driverId, forKey: .driverId)
        try container.encodeIfPresent(driverName, forKey: .driverName)
        try container.encodeIfPresent(volumeAdjustmentProposed, forKey: .volumeAdjustmentProposed)
        try container.encodeIfPresent(adjustedPrice, forKey: .adjustedPrice)
        try container.encodeIfPresent(adjustedVolume, forKey: .adjustedVolume)
        try container.encodeIfPresent(address, forKey: .address)
    }

    /// Whether this job was delegated to an operator
    var isDelegated: Bool {
        operatorId != nil && !operatorId!.isEmpty
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

// MARK: - Referral Code Response
struct ReferralCodeResponse: Codable {
    let success: Bool
    let referralCode: String
    let totalReferrals: Int?
    let creditsEarned: Double?

    enum CodingKeys: String, CodingKey {
        case success
        case referralCode = "referral_code"
        case totalReferrals = "total_referrals"
        case creditsEarned = "credits_earned"
    }
}

// MARK: - Generic API Response
struct APIResponse<T: Codable>: Codable {
    let success: Bool
    let data: T?
    let error: String?
}

// MARK: - User Model
struct User: Codable {
    let id: String
    let name: String?
    let email: String?
    let phoneNumber: String?
    let role: String?

    var displayName: String {
        if let name = name, !name.isEmpty {
            return name
        }
        if let email = email {
            return email
        }
        return "User"
    }
}

// MARK: - Auth Response
struct AuthResponse: Codable {
    let success: Bool
    let token: String
    let user: User
}

// MARK: - Auth Refresh Response
struct AuthRefreshResponse: Codable {
    let success: Bool
    let token: String
}

// MARK: - Validate Token Response
struct ValidateTokenResponse: Codable {
    let success: Bool
    let user: User
}

// MARK: - Job Creation Response
struct JobCreationResponse: Codable {
    let success: Bool
    let jobId: String?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case success
        case jobId = "job_id"
        case message
    }
}

// MARK: - Job Status Response
struct JobStatusResponse: Codable {
    let success: Bool
    let booking: BookingStatusDetail
}

struct BookingStatusDetail: Codable {
    let id: String
    let status: String
    let address: String
    let driverName: String?
    let driverTruckType: String?
    let totalPrice: Double
    let scheduledAt: String?

    enum CodingKeys: String, CodingKey {
        case id, status, address
        case driverName = "driver_name"
        case driverTruckType = "driver_truck_type"
        case totalPrice = "total_price"
        case scheduledAt = "scheduled_at"
    }
}
