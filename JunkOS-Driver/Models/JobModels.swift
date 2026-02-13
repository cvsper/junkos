//
//  JobModels.swift
//  Umuve Pro
//
//  Job-related data models matching backend API contracts.
//

import Foundation
import SwiftUI

// MARK: - Job Status

enum JobStatus: String, Codable, CaseIterable {
    case pending
    case confirmed
    case assigned
    case accepted
    case enRoute = "en_route"
    case arrived
    case started
    case completed
    case cancelled

    var displayName: String {
        switch self {
        case .pending: return "Pending"
        case .confirmed: return "Confirmed"
        case .assigned: return "Assigned"
        case .accepted: return "Accepted"
        case .enRoute: return "En Route"
        case .arrived: return "Arrived"
        case .started: return "In Progress"
        case .completed: return "Completed"
        case .cancelled: return "Cancelled"
        }
    }

    var color: Color {
        switch self {
        case .pending: return .statusPending
        case .confirmed: return .statusPending
        case .assigned: return .statusAccepted
        case .accepted: return .statusAccepted
        case .enRoute: return .statusEnRoute
        case .arrived: return .statusArrived
        case .started: return .statusStarted
        case .completed: return .statusCompleted
        case .cancelled: return .statusCancelled
        }
    }

    var icon: String {
        switch self {
        case .pending: return "clock"
        case .confirmed: return "checkmark.circle"
        case .assigned: return "person.badge.clock"
        case .accepted: return "checkmark.circle"
        case .enRoute: return "car.fill"
        case .arrived: return "mappin.circle.fill"
        case .started: return "hammer.fill"
        case .completed: return "checkmark.seal.fill"
        case .cancelled: return "xmark.circle.fill"
        }
    }

    /// Whether this status means the job is actively assigned to this driver.
    var isAssignedToDriver: Bool {
        switch self {
        case .assigned, .accepted, .enRoute, .arrived, .started:
            return true
        default:
            return false
        }
    }

    /// The lifecycle steps displayed in the stepper (excludes pending/confirmed/cancelled).
    static var lifecycleSteps: [JobStatus] {
        [.assigned, .accepted, .enRoute, .arrived, .started, .completed]
    }

    var stepIndex: Int {
        Self.lifecycleSteps.firstIndex(of: self) ?? 0
    }
}

// MARK: - Driver Job

struct DriverJob: Codable, Identifiable {
    let id: String
    let customerId: String
    let driverId: String?
    let status: String
    let address: String
    let lat: Double?
    let lng: Double?
    let items: [String]?
    let volumeEstimate: Double?
    let photos: [String]
    let beforePhotos: [String]
    let afterPhotos: [String]
    let scheduledAt: String?
    let startedAt: String?
    let completedAt: String?
    let basePrice: Double
    let itemTotal: Double
    let volumePrice: Double
    let serviceFee: Double
    let surgeMultiplier: Double
    let totalPrice: Double
    let notes: String?
    let createdAt: String?
    let updatedAt: String?

    // Added by available-jobs endpoint
    let distanceKm: Double?

    enum CodingKeys: String, CodingKey {
        case id
        case customerId = "customer_id"
        case driverId = "driver_id"
        case status, address, lat, lng, items
        case volumeEstimate = "volume_estimate"
        case photos
        case beforePhotos = "before_photos"
        case afterPhotos = "after_photos"
        case scheduledAt = "scheduled_at"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case basePrice = "base_price"
        case itemTotal = "item_total"
        case volumePrice = "volume_price"
        case serviceFee = "service_fee"
        case surgeMultiplier = "surge_multiplier"
        case totalPrice = "total_price"
        case notes
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case distanceKm = "distance_km"
    }

    var jobStatus: JobStatus {
        JobStatus(rawValue: status) ?? .pending
    }

    var distanceMiles: Double? {
        guard let km = distanceKm else { return nil }
        return km * 0.621371
    }

    var formattedDistance: String {
        guard let miles = distanceMiles else { return "N/A" }
        return String(format: "%.1f mi", miles)
    }

    var formattedPrice: String {
        String(format: "$%.0f", totalPrice)
    }

    var shortAddress: String {
        address.components(separatedBy: ",").first ?? address
    }

    var scheduledDate: Date? {
        guard let str = scheduledAt else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: str) ?? ISO8601DateFormatter().date(from: str)
    }
}

// MARK: - API Responses

struct AvailableJobsResponse: Codable {
    let success: Bool
    let jobs: [DriverJob]
}

struct JobActionResponse: Codable {
    let success: Bool
    let job: DriverJob
}

// MARK: - Status Update

struct StatusUpdateRequest: Codable {
    let status: String
    let beforePhotos: [String]?
    let afterPhotos: [String]?

    enum CodingKeys: String, CodingKey {
        case status
        case beforePhotos = "before_photos"
        case afterPhotos = "after_photos"
    }
}
