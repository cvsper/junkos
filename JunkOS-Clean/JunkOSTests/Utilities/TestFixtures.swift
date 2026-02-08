//
//  TestFixtures.swift
//  JunkOSTests
//
//  Sample data fixtures for testing
//

import Foundation
@testable import JunkOS

struct TestFixtures {
    
    // MARK: - Address Fixtures
    static let validAddress = Address(
        street: "123 Main St",
        unit: "Apt 4B",
        city: "Tampa",
        state: "FL",
        zipCode: "33602"
    )
    
    static let invalidAddress = Address(
        street: "",
        unit: "",
        city: "",
        state: "FL",
        zipCode: ""
    )
    
    static let partialAddress = Address(
        street: "456 Oak Ave",
        unit: "",
        city: "Tampa",
        state: "FL",
        zipCode: ""
    )
    
    // MARK: - BookingData Fixtures
    static func createBookingData(
        address: Address = validAddress,
        photos: [Data] = [],
        selectedServices: Set<String> = ["furniture", "appliances"],
        serviceDetails: String = "Large couch and refrigerator",
        selectedDate: Date? = Date(),
        selectedTimeSlot: String? = "morning"
    ) -> BookingData {
        let booking = BookingData()
        booking.address = address
        booking.photos = photos
        booking.selectedServices = selectedServices
        booking.serviceDetails = serviceDetails
        booking.selectedDate = selectedDate
        booking.selectedTimeSlot = selectedTimeSlot
        return booking
    }
    
    static var completeBooking: BookingData {
        createBookingData(
            address: validAddress,
            photos: [samplePhotoData],
            selectedServices: ["furniture", "appliances"],
            serviceDetails: "Large items for removal",
            selectedDate: Date(),
            selectedTimeSlot: "morning"
        )
    }
    
    static var incompleteBooking: BookingData {
        createBookingData(
            address: invalidAddress,
            photos: [],
            selectedServices: [],
            serviceDetails: "",
            selectedDate: nil,
            selectedTimeSlot: nil
        )
    }
    
    // MARK: - Photo Fixtures
    static var samplePhotoData: Data {
        // Create a simple 1x1 pixel image data
        return Data([0xFF, 0xD8, 0xFF, 0xE0]) // JPEG header
    }
    
    static var multiplePhotos: [Data] {
        return [samplePhotoData, samplePhotoData, samplePhotoData]
    }
    
    // MARK: - Service Fixtures
    static let popularServices = Service.all.filter { $0.isPopular }
    static let allServices = Service.all
    static let singleService = Service.all.first!
    
    // MARK: - TimeSlot Fixtures
    static let availableTimeSlots = TimeSlot.slots.filter { $0.isAvailable }
    static let recommendedTimeSlots = TimeSlot.slots.filter { $0.isRecommended }
    static let allTimeSlots = TimeSlot.slots
    
    // MARK: - Date Fixtures
    static var today: Date {
        Calendar.current.startOfDay(for: Date())
    }
    
    static var tomorrow: Date {
        Calendar.current.date(byAdding: .day, value: 1, to: today)!
    }
    
    static var nextWeek: Date {
        Calendar.current.date(byAdding: .day, value: 7, to: today)!
    }
    
    static var pastDate: Date {
        Calendar.current.date(byAdding: .day, value: -1, to: today)!
    }
}
