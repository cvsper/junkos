//
//  MockAPIClient.swift
//  JunkOSTests
//
//  Mock API client for future backend integration testing
//

import Foundation
import Combine
@testable import JunkOS

// MARK: - API Client Protocol
protocol APIClientProtocol {
    func submitBooking(_ booking: BookingData) async throws -> BookingResponse
    func uploadPhotos(_ photos: [Data]) async throws -> [String]
    func checkAvailability(date: Date, zipCode: String) async throws -> [TimeSlot]
}

// MARK: - Booking Response
struct BookingResponse: Codable {
    let id: String
    let confirmationNumber: String
    let status: String
    let estimatedArrival: Date?
}

// MARK: - Mock API Client
class MockAPIClient: APIClientProtocol {
    // MARK: - Mock Properties
    var shouldSucceed = true
    var mockBookingResponse = BookingResponse(
        id: "booking-123",
        confirmationNumber: "JOS-2026-001",
        status: "confirmed",
        estimatedArrival: Date()
    )
    var mockPhotoURLs = ["https://example.com/photo1.jpg", "https://example.com/photo2.jpg"]
    var mockTimeSlots = TimeSlot.slots
    var mockError: Error?
    
    // MARK: - Call Tracking
    var submitBookingCalled = false
    var uploadPhotosCalled = false
    var checkAvailabilityCalled = false
    var lastSubmittedBooking: BookingData?
    var lastUploadedPhotos: [Data]?
    var lastAvailabilityDate: Date?
    var lastAvailabilityZipCode: String?
    
    // MARK: - API Methods
    func submitBooking(_ booking: BookingData) async throws -> BookingResponse {
        submitBookingCalled = true
        lastSubmittedBooking = booking
        
        if shouldSucceed {
            return mockBookingResponse
        } else {
            throw mockError ?? NSError(
                domain: "MockAPIClient",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Mock booking submission failed"]
            )
        }
    }
    
    func uploadPhotos(_ photos: [Data]) async throws -> [String] {
        uploadPhotosCalled = true
        lastUploadedPhotos = photos
        
        if shouldSucceed {
            return mockPhotoURLs
        } else {
            throw mockError ?? NSError(
                domain: "MockAPIClient",
                code: -2,
                userInfo: [NSLocalizedDescriptionKey: "Mock photo upload failed"]
            )
        }
    }
    
    func checkAvailability(date: Date, zipCode: String) async throws -> [TimeSlot] {
        checkAvailabilityCalled = true
        lastAvailabilityDate = date
        lastAvailabilityZipCode = zipCode
        
        if shouldSucceed {
            return mockTimeSlots
        } else {
            throw mockError ?? NSError(
                domain: "MockAPIClient",
                code: -3,
                userInfo: [NSLocalizedDescriptionKey: "Mock availability check failed"]
            )
        }
    }
    
    // MARK: - Helper Methods
    func reset() {
        shouldSucceed = true
        submitBookingCalled = false
        uploadPhotosCalled = false
        checkAvailabilityCalled = false
        lastSubmittedBooking = nil
        lastUploadedPhotos = nil
        lastAvailabilityDate = nil
        lastAvailabilityZipCode = nil
        mockError = nil
    }
}
