//
//  ContractorModels.swift
//  JunkOS Driver
//
//  Contractor profile and registration models.
//

import Foundation

// MARK: - Truck Type

enum TruckType: String, Codable, CaseIterable, Identifiable {
    case pickup = "pickup"
    case cargoVan = "cargo_van"
    case boxTruck = "box_truck"
    case dumpTrailer = "dump_trailer"
    case flatbed = "flatbed"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .pickup: return "Pickup Truck"
        case .cargoVan: return "Cargo Van"
        case .boxTruck: return "Box Truck"
        case .dumpTrailer: return "Dump Trailer"
        case .flatbed: return "Flatbed"
        }
    }

    var icon: String {
        switch self {
        case .pickup: return "truck.pickup.side"
        case .cargoVan: return "car.side"
        case .boxTruck: return "box.truck"
        case .dumpTrailer: return "truck.box"
        case .flatbed: return "truck.box.badge.clock"
        }
    }

    var capacityLabel: String {
        switch self {
        case .pickup: return "Up to 2 cubic yards"
        case .cargoVan: return "Up to 4 cubic yards"
        case .boxTruck: return "Up to 10 cubic yards"
        case .dumpTrailer: return "Up to 15 cubic yards"
        case .flatbed: return "Up to 8 cubic yards"
        }
    }
}

// MARK: - Approval Status

enum ApprovalStatus: String, Codable {
    case pending
    case approved
    case rejected
}

// MARK: - Contractor Profile

struct ContractorProfile: Codable, Identifiable {
    let id: String
    let userId: String
    let licenseUrl: String?
    let insuranceUrl: String?
    let truckPhotos: [String]
    let truckType: String?
    let truckCapacity: Double?
    let stripeConnectId: String?
    let isOnline: Bool
    let currentLat: Double?
    let currentLng: Double?
    let avgRating: Double
    let totalJobs: Int
    let approvalStatus: String
    let availabilitySchedule: [String: [String]]?
    let createdAt: String?
    let updatedAt: String?

    // Nested user data from backend
    let user: DriverUser?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case licenseUrl = "license_url"
        case insuranceUrl = "insurance_url"
        case truckPhotos = "truck_photos"
        case truckType = "truck_type"
        case truckCapacity = "truck_capacity"
        case stripeConnectId = "stripe_connect_id"
        case isOnline = "is_online"
        case currentLat = "current_lat"
        case currentLng = "current_lng"
        case avgRating = "avg_rating"
        case totalJobs = "total_jobs"
        case approvalStatus = "approval_status"
        case availabilitySchedule = "availability_schedule"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case user
    }

    var approval: ApprovalStatus {
        ApprovalStatus(rawValue: approvalStatus) ?? .pending
    }
}

struct ContractorProfileResponse: Codable {
    let success: Bool
    let contractor: ContractorProfile
}

// MARK: - Registration Request

struct RegistrationRequest: Codable {
    let truckType: String
    let truckCapacity: Double?
    let licenseUrl: String?
    let insuranceUrl: String?
    let truckPhotos: [String]?

    enum CodingKeys: String, CodingKey {
        case truckType = "truck_type"
        case truckCapacity = "truck_capacity"
        case licenseUrl = "license_url"
        case insuranceUrl = "insurance_url"
        case truckPhotos = "truck_photos"
    }
}

struct RegistrationResponse: Codable {
    let success: Bool
    let contractor: ContractorProfile
}

// MARK: - Availability

struct AvailabilityRequest: Codable {
    let isOnline: Bool?
    let availabilitySchedule: [String: [String]]?

    enum CodingKeys: String, CodingKey {
        case isOnline = "is_online"
        case availabilitySchedule = "availability_schedule"
    }
}

struct AvailabilityResponse: Codable {
    let success: Bool
    let contractor: ContractorProfile
}

// MARK: - Location Update

struct LocationUpdateRequest: Codable {
    let lat: Double
    let lng: Double
}

struct LocationUpdateResponse: Codable {
    let success: Bool
    let lat: Double
    let lng: Double
}
