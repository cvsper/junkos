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

    var description: String {
        switch self {
        case .junkRemoval:
            return "Furniture, appliances, yard waste — we haul it all"
        }
    }

    var icon: String {
        switch self {
        case .junkRemoval:
            return "truck.box.fill"
        }
    }
}

// MARK: - Pricing Estimate
// Mirrors the /api/pricing/estimate response (snake_case → camelCase via
// JSONDecoder.keyDecodingStrategy = .convertFromSnakeCase). Most fields are
// optional because the backend may omit them when irrelevant (e.g. no surge).
struct PricingEstimate: Codable {
    let total: Double
    let itemsSubtotal: Double?
    let basePrice: Double?
    let volumeDiscount: Double?
    let volumeDiscountLabel: String?
    let surgeMultiplier: Double?
    let surgeAmount: Double?
    let surgeReasons: [String]?
    let serviceFee: Double?
    let recyclingFees: Double?
    let laborFee: Double?
    let minimumApplied: Bool?
    let minimumJobPrice: Double?
    let estimatedDuration: Int?
    let truckSize: String?
    let totalQuantity: Int?

    // Convenience accessors used by views — fall back gracefully when the
    // backend omits an optional field.
    var subtotal: Double { basePrice ?? itemsSubtotal ?? total }
    var estimatedDurationMinutes: Int { estimatedDuration ?? 0 }
    var recommendedTruck: String { truckSize ?? "" }
}

// MARK: - Item Category
// Mirrors the seven categories shown on the web booking flow's Items step.
// Display name + SF Symbol icon + the backend's category key + per-category
// preset items (cu-ft + lbs estimates) live here so views and pricing share
// one source of truth.
enum ItemCategory: String, CaseIterable, Identifiable {
    case furniture
    case appliances
    case electronics
    case construction
    case yardWaste
    case generalJunk
    case other

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .furniture: return "Furniture"
        case .appliances: return "Appliances"
        case .electronics: return "Electronics"
        case .construction: return "Construction Debris"
        case .yardWaste: return "Yard Waste"
        case .generalJunk: return "General Junk"
        case .other: return "Other"
        }
    }

    var systemIcon: String {
        switch self {
        case .furniture: return "sofa.fill"
        case .appliances: return "refrigerator.fill"
        case .electronics: return "tv.fill"
        case .construction: return "hammer.fill"
        case .yardWaste: return "leaf.fill"
        case .generalJunk: return "trash.fill"
        case .other: return "shippingbox.fill"
        }
    }

    /// API key used in `/api/pricing/estimate` items payload.
    var apiKey: String {
        switch self {
        case .furniture: return "furniture"
        case .appliances: return "appliances"
        case .electronics: return "electronics"
        case .construction: return "construction"
        case .yardWaste: return "yard_waste"
        case .generalJunk: return "general"
        case .other: return "other"
        }
    }

    var presets: [ItemPreset] {
        switch self {
        case .furniture:
            return [
                ItemPreset(name: "Couch / Sofa", cuFt: 40, lbs: 150),
                ItemPreset(name: "Loveseat", cuFt: 25, lbs: 90),
                ItemPreset(name: "Recliner / Armchair", cuFt: 18, lbs: 70),
                ItemPreset(name: "Mattress (any size)", cuFt: 25, lbs: 60),
                ItemPreset(name: "Bed Frame", cuFt: 15, lbs: 50),
                ItemPreset(name: "Dresser", cuFt: 25, lbs: 120),
                ItemPreset(name: "Dining Table", cuFt: 30, lbs: 80),
                ItemPreset(name: "Dining Chair", cuFt: 8, lbs: 20),
                ItemPreset(name: "Desk", cuFt: 20, lbs: 70),
                ItemPreset(name: "Bookshelf", cuFt: 15, lbs: 60),
            ]
        case .appliances:
            return [
                ItemPreset(name: "Refrigerator", cuFt: 35, lbs: 250),
                ItemPreset(name: "Stove / Oven", cuFt: 25, lbs: 180),
                ItemPreset(name: "Washer", cuFt: 18, lbs: 200),
                ItemPreset(name: "Dryer", cuFt: 18, lbs: 130),
                ItemPreset(name: "Dishwasher", cuFt: 15, lbs: 80),
                ItemPreset(name: "Microwave", cuFt: 5, lbs: 35),
                ItemPreset(name: "Water Heater", cuFt: 12, lbs: 130),
                ItemPreset(name: "AC Unit (window)", cuFt: 6, lbs: 60),
            ]
        case .electronics:
            return [
                ItemPreset(name: "TV (50\"+)", cuFt: 10, lbs: 40),
                ItemPreset(name: "TV (under 50\")", cuFt: 6, lbs: 25),
                ItemPreset(name: "Monitor", cuFt: 4, lbs: 12),
                ItemPreset(name: "Computer / Tower", cuFt: 3, lbs: 20),
                ItemPreset(name: "Printer / Copier", cuFt: 4, lbs: 18),
                ItemPreset(name: "Stereo / Speaker", cuFt: 4, lbs: 15),
                ItemPreset(name: "Old electronics (mixed)", cuFt: 5, lbs: 20),
            ]
        case .construction:
            return [
                ItemPreset(name: "Drywall sheets / bags", cuFt: 8, lbs: 50),
                ItemPreset(name: "Lumber / scrap wood", cuFt: 10, lbs: 40),
                ItemPreset(name: "Carpet / flooring (rolled)", cuFt: 15, lbs: 50),
                ItemPreset(name: "Toilet / sink", cuFt: 12, lbs: 70),
                ItemPreset(name: "Cabinets", cuFt: 20, lbs: 60),
                ItemPreset(name: "Concrete / bricks (per bag)", cuFt: 3, lbs: 60),
                ItemPreset(name: "Tile / debris (per bag)", cuFt: 4, lbs: 40),
            ]
        case .yardWaste:
            return [
                ItemPreset(name: "Bags of leaves / clippings", cuFt: 6, lbs: 30),
                ItemPreset(name: "Branches (small bundle)", cuFt: 8, lbs: 30),
                ItemPreset(name: "Tree limbs (large)", cuFt: 15, lbs: 60),
                ItemPreset(name: "Tree stump", cuFt: 20, lbs: 200),
                ItemPreset(name: "Sod / dirt (per bag)", cuFt: 3, lbs: 50),
                ItemPreset(name: "Patio furniture", cuFt: 25, lbs: 60),
                ItemPreset(name: "Pool toys / equipment", cuFt: 15, lbs: 40),
            ]
        case .generalJunk:
            return [
                ItemPreset(name: "Boxes / trash bags", cuFt: 4, lbs: 20),
                ItemPreset(name: "Clothing / textiles", cuFt: 4, lbs: 15),
                ItemPreset(name: "Toys / kids items", cuFt: 6, lbs: 20),
                ItemPreset(name: "Books / magazines", cuFt: 4, lbs: 35),
                ItemPreset(name: "Kitchenware / dishes", cuFt: 4, lbs: 25),
                ItemPreset(name: "Misc household items", cuFt: 6, lbs: 25),
            ]
        case .other:
            return [
                ItemPreset(name: "Hot tub", cuFt: 80, lbs: 450),
                ItemPreset(name: "Piano (upright)", cuFt: 50, lbs: 500),
                ItemPreset(name: "Piano (grand)", cuFt: 100, lbs: 700),
                ItemPreset(name: "Pool table", cuFt: 60, lbs: 700),
                ItemPreset(name: "Safe", cuFt: 8, lbs: 250),
                ItemPreset(name: "Custom — describe in notes", cuFt: 10, lbs: 30),
            ]
        }
    }
}

// MARK: - Item Preset

struct ItemPreset: Identifiable, Hashable {
    let name: String
    let cuFt: Double
    let lbs: Double
    var id: String { name }
}

// MARK: - Booking Item

struct BookingItem: Identifiable, Equatable {
    let id: UUID
    var category: ItemCategory
    var name: String
    var quantity: Int
    var cuFtPerUnit: Double
    var lbsPerUnit: Double

    init(category: ItemCategory, preset: ItemPreset, quantity: Int = 1) {
        self.id = UUID()
        self.category = category
        self.name = preset.name
        self.quantity = quantity
        self.cuFtPerUnit = preset.cuFt
        self.lbsPerUnit = preset.lbs
    }

    var totalCuFt: Double { cuFtPerUnit * Double(quantity) }
    var totalLbs: Double { lbsPerUnit * Double(quantity) }
}

// MARK: - Truck Load Tiers
// Hardcoded volume tiers + base prices matching the web booking flow.
// Pricing is "by truck space used, not by item count" — the active tier is
// determined by the total cu ft across the user's selected items.

struct TruckLoadTier: Equatable {
    let label: String
    let maxCuFt: Double
    let basePrice: Double

    static let all: [TruckLoadTier] = [
        TruckLoadTier(label: "1/8 Truck", maxCuFt: 56, basePrice: 89),
        TruckLoadTier(label: "1/4 Truck", maxCuFt: 112, basePrice: 149),
        TruckLoadTier(label: "1/2 Truck", maxCuFt: 225, basePrice: 249),
        TruckLoadTier(label: "3/4 Truck", maxCuFt: 337, basePrice: 399),
        TruckLoadTier(label: "Full Truck", maxCuFt: 450, basePrice: 599),
    ]

    static let maxCapacityCuFt: Double = 450

    static func tier(forCuFt cuFt: Double) -> TruckLoadTier {
        all.first { cuFt <= $0.maxCuFt } ?? all.last!
    }
}

// MARK: - Booking Data
class BookingData: ObservableObject {
    // Service selection
    @Published var serviceType: ServiceType?

    // Items (web booking flow Step 3 — replaces the legacy volumeTier picker)
    @Published var items: [BookingItem] = []
    @Published var notes: String = ""

    // Location fields
    @Published var address: Address = Address()  // Pickup address
    @Published var pickupCoordinate: CLLocationCoordinate2D?

    // Pricing fields
    @Published var estimatedDistance: Double?  // miles
    @Published var estimatedPrice: Double?
    @Published var priceBreakdown: PricingEstimate?

    // Promo (web booking flow Step 6)
    @Published var promoCode: String = ""
    @Published var promoApplied: Bool = false
    @Published var promoDiscount: Double = 0

    // Estimate acceptance (web booking flow Step 5 checkbox)
    @Published var estimateAccepted: Bool = false

    // Media and scheduling
    @Published var photos: [Data] = []
    @Published var selectedDate: Date?
    @Published var selectedTimeSlot: String?
    @Published var serviceDetails: String = ""

    // Navigation signal
    @Published var bookingCompleted = false

    // Derived: total cubic feet across all items (drives truck tier + UI bar)
    var totalCuFt: Double { items.reduce(0) { $0 + $1.totalCuFt } }
    var totalLbs: Double { items.reduce(0) { $0 + $1.totalLbs } }
    var totalQuantity: Int { items.reduce(0) { $0 + $1.quantity } }
    var currentTruckTier: TruckLoadTier { TruckLoadTier.tier(forCuFt: totalCuFt) }
    var hasItems: Bool { !items.isEmpty }

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
        // Web parity: a booking is "configured" once the user has selected at
        // least one item to be hauled. Service type is implicit (junk removal
        // is the only service offered) and is pre-seeded by the wizard.
        hasItems
    }

    // MARK: - Methods

    func reset() {
        serviceType = nil
        items = []
        notes = ""
        address = Address()
        pickupCoordinate = nil
        estimatedDistance = nil
        estimatedPrice = nil
        priceBreakdown = nil
        promoCode = ""
        promoApplied = false
        promoDiscount = 0
        estimateAccepted = false
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
        // Slot labels match the web booking flow's Schedule step verbatim:
        // 8-10 AM, 10 AM-12 PM, 12-2 PM, 2-4 PM, 4-6 PM. IDs encode the
        // start/end hours in 24-hour form so the parser in
        // DateTimePickerViewModel.formattedScheduledDateTime can derive
        // a canonical "HH:00" string for the API.
        TimeSlot(id: "8-10", time: "8-10 AM", isRecommended: true, isAvailable: true),
        TimeSlot(id: "10-12", time: "10 AM-12 PM", isRecommended: true, isAvailable: true),
        TimeSlot(id: "12-14", time: "12-2 PM", isRecommended: false, isAvailable: true),
        TimeSlot(id: "14-16", time: "2-4 PM", isRecommended: false, isAvailable: true),
        TimeSlot(id: "16-18", time: "4-6 PM", isRecommended: false, isAvailable: true)
    ]
}

// MARK: - Service
// Local model returned by APIService.toService() — used by services screens to
// render API-provided service catalogs.
struct Service: Identifiable, Hashable {
    let id: String
    let name: String
    let icon: String
    let price: String
    let isPopular: Bool

    static let all: [Service] = []
}
