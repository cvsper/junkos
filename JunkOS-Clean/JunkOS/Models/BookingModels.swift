//
//  BookingModels.swift
//  Umuve
//
//  Data models for the booking flow
//

import Foundation
import SwiftUI
import CoreLocation

// MARK: - Service Type
enum ServiceType: String, CaseIterable {
    case junkRemoval = "Junk Removal"
    case autoTransport = "Auto Transport"

    var description: String {
        switch self {
        case .junkRemoval:
            return "Furniture, appliances, yard waste — we haul it all"
        case .autoTransport:
            return "Vehicle pickup and delivery anywhere"
        }
    }

    var icon: String {
        switch self {
        case .junkRemoval:
            return "truck.box.fill"
        case .autoTransport:
            return "car.fill"
        }
    }
}

// MARK: - Volume Tier
enum VolumeTier: String, CaseIterable {
    case quarter = "1/4 Truck"
    case half = "1/2 Truck"
    case threeQuarter = "3/4 Truck"
    case full = "Full Truck"

    var fillLevel: Double {
        switch self {
        case .quarter:
            return 0.25
        case .half:
            return 0.5
        case .threeQuarter:
            return 0.75
        case .full:
            return 1.0
        }
    }

    var description: String {
        switch self {
        case .quarter:
            return "A few items"
        case .half:
            return "Small room"
        case .threeQuarter:
            return "Large room"
        case .full:
            return "Whole house"
        }
    }

    var icon: String {
        switch self {
        case .quarter:
            return "square.stack.fill"
        case .half:
            return "cube.fill"
        case .threeQuarter:
            return "shippingbox.fill"
        case .full:
            return "truck.box.fill"
        }
    }
}

// MARK: - Pricing Estimate
struct PricingEstimate: Codable {
    let subtotal: Double
    let serviceFee: Double
    let volumeDiscount: Double
    let timeSurge: Double
    let zoneSurge: Double
    let total: Double
    let estimatedDurationMinutes: Int
    let recommendedTruck: String
}

// MARK: - Booking Data
class BookingData: ObservableObject {
    // Service selection
    @Published var serviceType: ServiceType?

    // Junk Removal fields
    @Published var volumeTier: VolumeTier = .half

    // Auto Transport fields
    @Published var vehicleMake: String = ""
    @Published var vehicleModel: String = ""
    @Published var vehicleYear: String = ""
    @Published var isVehicleRunning: Bool = true
    @Published var needsEnclosedTrailer: Bool = false

    // Location fields
    @Published var address: Address = Address()  // Pickup address
    @Published var pickupCoordinate: CLLocationCoordinate2D?
    @Published var dropoffAddress: Address = Address()  // Auto Transport only
    @Published var dropoffCoordinate: CLLocationCoordinate2D?

    // Pricing fields
    @Published var estimatedDistance: Double?  // miles
    @Published var estimatedPrice: Double?
    @Published var priceBreakdown: PricingEstimate?

    // Media and scheduling
    @Published var photos: [Data] = []
    @Published var selectedDate: Date?
    @Published var selectedTimeSlot: String?
    @Published var serviceDetails: String = ""

    // Navigation signal
    @Published var bookingCompleted = false

    // MARK: - Legacy Properties (TEMPORARY - Phase 2 refactor)
    // TODO: Phase 2 refactor - Remove once old views (WelcomeView, PaymentView, ConfirmationView) are refactored
    @Published var isCommercialBooking: Bool = false
    @Published var customerEmail: String = ""
    @Published var customerName: String = ""
    @Published var customerPhone: String = ""
    @Published var serviceTier: ServiceTier = .fullService
    @Published var selectedServices: Set<String> = []
    @Published var dontNeedToBeHome: Bool = false
    @Published var outdoorPlacementInstructions: String = ""
    @Published var loaderNotes: String = ""
    @Published var businessName: String = ""
    @Published var isRecurringPickup: Bool = false
    @Published var recurringFrequency: RecurringFrequency = .weekly
    @Published var referralCode: String = ""

    // MARK: - Computed Properties

    var isAddressValid: Bool {
        !address.street.isEmpty && !address.city.isEmpty && !address.zipCode.isEmpty
    }

    var hasPhotos: Bool {
        !photos.isEmpty
    }

    var hasSelectedDateTime: Bool {
        selectedDate != nil && selectedTimeSlot != nil
    }

    var isServiceConfigured: Bool {
        guard let serviceType = serviceType else { return false }

        switch serviceType {
        case .junkRemoval:
            return true  // volumeTier always has default
        case .autoTransport:
            return !vehicleMake.isEmpty && !vehicleModel.isEmpty && !vehicleYear.isEmpty
        }
    }

    var needsDropoff: Bool {
        serviceType == .autoTransport
    }

    // MARK: - Methods

    func reset() {
        serviceType = nil
        volumeTier = .half
        vehicleMake = ""
        vehicleModel = ""
        vehicleYear = ""
        isVehicleRunning = true
        needsEnclosedTrailer = false
        address = Address()
        pickupCoordinate = nil
        dropoffAddress = Address()
        dropoffCoordinate = nil
        estimatedDistance = nil
        estimatedPrice = nil
        priceBreakdown = nil
        photos = []
        selectedDate = nil
        selectedTimeSlot = nil
        serviceDetails = ""
        bookingCompleted = false
    }
}

// MARK: - Address
struct Address {
    var street: String = ""
    var unit: String = ""
    var city: String = ""
    var state: String = "FL"
    var zipCode: String = ""

    var fullAddress: String {
        var parts = [street]
        if !unit.isEmpty { parts.append("Unit \(unit)") }
        parts.append("\(city), \(state) \(zipCode)")
        return parts.joined(separator: ", ")
    }
}

// MARK: - Time Slot
struct TimeSlot: Identifiable {
    let id: String
    let time: String
    let isRecommended: Bool
    let isAvailable: Bool

    static let slots: [TimeSlot] = [
        TimeSlot(id: "morning", time: "8:00 AM - 10:00 AM", isRecommended: true, isAvailable: true),
        TimeSlot(id: "midmorning", time: "10:00 AM - 12:00 PM", isRecommended: true, isAvailable: true),
        TimeSlot(id: "afternoon", time: "12:00 PM - 2:00 PM", isRecommended: false, isAvailable: true),
        TimeSlot(id: "midafternoon", time: "2:00 PM - 4:00 PM", isRecommended: false, isAvailable: false),
        TimeSlot(id: "evening", time: "4:00 PM - 6:00 PM", isRecommended: false, isAvailable: true)
    ]
}

// MARK: - Legacy Types (TEMPORARY - Phase 2 refactor)
// TODO: Phase 2 refactor - Remove once PaymentView, ServiceSelectionView, ConfirmationViewModel, and APIModels are refactored

struct PriceBreakdown {
    let basePrice: Double = 89.00
    let itemsCharge: Double = 45.00
    let disposalFee: Double = 15.00
    let serviceTier: ServiceTier
    let isCommercial: Bool

    init(serviceTier: ServiceTier = .fullService, isCommercial: Bool = false) {
        self.serviceTier = serviceTier
        self.isCommercial = isCommercial
    }

    var subtotal: Double { basePrice + itemsCharge + disposalFee }
    var tierDiscount: Double { 0.0 }
    var commercialDiscount: Double { 0.0 }
    var total: Double { subtotal }
}

struct Service: Identifiable, Hashable {
    let id: String
    let name: String
    let icon: String
    let price: String
    let isPopular: Bool

    static let all: [Service] = []
}

enum ServiceTier: String, CaseIterable {
    case fullService = "Full-Service"
    case curbside = "Curbside Pickup"
}

enum RecurringFrequency: String, CaseIterable {
    case weekly = "Weekly"
    case biweekly = "Bi-weekly"
    case monthly = "Monthly"
}
