//
//  BookingModels.swift
//  Umuve
//
//  Data models for the booking flow
//

import Foundation
import SwiftUI

// MARK: - Service Tier (LoadUp Feature #1)
enum ServiceTier: String, CaseIterable {
    case fullService = "Full-Service"
    case curbside = "Curbside Pickup"
    
    var description: String {
        switch self {
        case .fullService:
            return "In-home pickup with heavy lifting"
        case .curbside:
            return "20-30% discount • Contactless • No need to be home"
        }
    }
    
    var discountMultiplier: Double {
        switch self {
        case .fullService:
            return 1.0
        case .curbside:
            return 0.75 // 25% discount
        }
    }
}

// MARK: - Booking Data
class BookingData: ObservableObject {
    @Published var address: Address = Address()
    @Published var photos: [Data] = []  // Photo data
    @Published var selectedServices: Set<String> = []
    @Published var serviceDetails: String = ""
    @Published var selectedDate: Date?
    @Published var selectedTimeSlot: String?
    
    // LoadUp Feature #1: Service Tier
    @Published var serviceTier: ServiceTier = .fullService
    
    // LoadUp Feature #2: Don't Need to Be Home
    @Published var dontNeedToBeHome: Bool = false
    @Published var outdoorPlacementInstructions: String = ""
    @Published var loaderNotes: String = ""
    
    // LoadUp Feature #4: Commercial Booking
    @Published var isCommercialBooking: Bool = false
    @Published var businessName: String = ""
    @Published var isRecurringPickup: Bool = false
    @Published var recurringFrequency: RecurringFrequency = .weekly
    
    // LoadUp Feature #5: Property Cleanout
    @Published var isPropertyCleanout: Bool = false
    @Published var selectedRooms: Set<String> = []
    @Published var cleanoutType: CleanoutType = .general
    
    // LoadUp Feature #6: Enhanced Service Details
    @Published var selectedItems: Set<String> = []
    @Published var beforePhotos: [Data] = []
    @Published var estimatedWeight: WeightCategory = .medium

    // Referral code (loaded from stored referral or entered manually)
    @Published var referralCode: String = ""

    // Customer info (filled during confirmation step)
    @Published var customerName: String = ""
    @Published var customerEmail: String = ""
    @Published var customerPhone: String = ""
    
    var isAddressValid: Bool {
        !address.street.isEmpty && !address.city.isEmpty && !address.zipCode.isEmpty
    }
    
    var hasPhotos: Bool {
        !photos.isEmpty
    }
    
    var hasSelectedServices: Bool {
        !selectedServices.isEmpty
    }
    
    var hasSelectedDateTime: Bool {
        selectedDate != nil && selectedTimeSlot != nil
    }
    
    // Navigation signal — set to true after successful booking to pop to root
    @Published var bookingCompleted = false

    func reset() {
        address = Address()
        photos = []
        selectedServices = []
        serviceDetails = ""
        selectedDate = nil
        selectedTimeSlot = nil
        serviceTier = .fullService
        dontNeedToBeHome = false
        outdoorPlacementInstructions = ""
        loaderNotes = ""
        isCommercialBooking = false
        businessName = ""
        isRecurringPickup = false
        recurringFrequency = .weekly
        isPropertyCleanout = false
        selectedRooms = []
        cleanoutType = .general
        selectedItems = []
        beforePhotos = []
        estimatedWeight = .medium
        referralCode = ""
        customerName = ""
        customerEmail = ""
        customerPhone = ""
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

// MARK: - Service
struct Service: Identifiable, Hashable {
    let id: String
    let name: String
    let icon: String  // SF Symbol name
    let price: String
    let isPopular: Bool
    let isPropertyCleanout: Bool
    
    init(id: String, name: String, icon: String, price: String, isPopular: Bool, isPropertyCleanout: Bool = false) {
        self.id = id
        self.name = name
        self.icon = icon
        self.price = price
        self.isPopular = isPopular
        self.isPropertyCleanout = isPropertyCleanout
    }
    
    static let all: [Service] = [
        Service(id: "furniture", name: "Furniture Removal", icon: "sofa.fill", price: "$99", isPopular: true),
        Service(id: "appliances", name: "Appliances", icon: "refrigerator.fill", price: "$89", isPopular: true),
        Service(id: "construction", name: "Construction Debris", icon: "hammer.fill", price: "$159", isPopular: false),
        Service(id: "electronics", name: "Electronics", icon: "tv.fill", price: "$69", isPopular: true),
        Service(id: "yard", name: "Yard Waste", icon: "leaf.fill", price: "$79", isPopular: false),
        Service(id: "general", name: "General Junk", icon: "trash.fill", price: "$89", isPopular: false),
        // LoadUp Feature #5: Property Cleanout Services
        Service(id: "property-cleanout", name: "Full Property Cleanout", icon: "house.fill", price: "Custom", isPopular: true, isPropertyCleanout: true)
    ]
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

// MARK: - Price Breakdown
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
    
    var subtotal: Double {
        basePrice + itemsCharge + disposalFee
    }
    
    var tierDiscount: Double {
        subtotal * (1.0 - serviceTier.discountMultiplier)
    }
    
    var commercialDiscount: Double {
        isCommercial ? subtotal * 0.15 : 0 // 15% bulk discount
    }
    
    var total: Double {
        subtotal - tierDiscount - commercialDiscount
    }
}

// MARK: - LoadUp Supporting Models

// Feature #4: Commercial Booking
enum RecurringFrequency: String, CaseIterable {
    case weekly = "Weekly"
    case biweekly = "Bi-weekly"
    case monthly = "Monthly"
}

// Feature #5: Property Cleanout
enum CleanoutType: String, CaseIterable {
    case general = "General Cleanout"
    case foreclosure = "Foreclosure"
    case eviction = "Eviction"
    case estate = "Estate Cleanout"
    
    var icon: String {
        switch self {
        case .general: return "house.fill"
        case .foreclosure: return "key.fill"
        case .eviction: return "door.left.hand.closed"
        case .estate: return "building.columns.fill"
        }
    }
}

struct RoomOption: Identifiable, Hashable {
    let id: String
    let name: String
    let icon: String
    
    static let all: [RoomOption] = [
        RoomOption(id: "living", name: "Living Room", icon: "sofa.fill"),
        RoomOption(id: "bedroom", name: "Bedroom", icon: "bed.double.fill"),
        RoomOption(id: "kitchen", name: "Kitchen", icon: "fork.knife"),
        RoomOption(id: "bathroom", name: "Bathroom", icon: "shower.fill"),
        RoomOption(id: "garage", name: "Garage", icon: "car.fill"),
        RoomOption(id: "basement", name: "Basement", icon: "arrow.down.to.line"),
        RoomOption(id: "attic", name: "Attic", icon: "arrow.up.to.line"),
        RoomOption(id: "yard", name: "Yard", icon: "leaf.fill")
    ]
}

// Feature #6: Enhanced Service Details
struct ItemOption: Identifiable, Hashable {
    let id: String
    let name: String
    let icon: String
    let estimatedWeight: String
    
    static let all: [ItemOption] = [
        ItemOption(id: "mattress", name: "Mattress", icon: "bed.double.fill", estimatedWeight: "50-100 lbs"),
        ItemOption(id: "couch", name: "Couch", icon: "sofa.fill", estimatedWeight: "100-200 lbs"),
        ItemOption(id: "fridge", name: "Refrigerator", icon: "refrigerator.fill", estimatedWeight: "200-300 lbs"),
        ItemOption(id: "washer", name: "Washer/Dryer", icon: "washer.fill", estimatedWeight: "150-250 lbs"),
        ItemOption(id: "tv", name: "TV", icon: "tv.fill", estimatedWeight: "20-80 lbs"),
        ItemOption(id: "desk", name: "Desk", icon: "square.and.pencil", estimatedWeight: "50-150 lbs"),
        ItemOption(id: "table", name: "Table", icon: "rectangle.fill", estimatedWeight: "40-100 lbs"),
        ItemOption(id: "chair", name: "Chairs", icon: "chair.fill", estimatedWeight: "10-30 lbs each")
    ]
}

enum WeightCategory: String, CaseIterable {
    case light = "Light (< 100 lbs)"
    case medium = "Medium (100-500 lbs)"
    case heavy = "Heavy (500-1000 lbs)"
    case extraHeavy = "Extra Heavy (1000+ lbs)"
    
    var icon: String {
        switch self {
        case .light: return "hand.raised.fill"
        case .medium: return "figure.walk"
        case .heavy: return "figure.strengthtraining.traditional"
        case .extraHeavy: return "figure.2.arms.open"
        }
    }
}
