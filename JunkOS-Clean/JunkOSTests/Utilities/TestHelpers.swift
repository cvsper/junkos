//
//  TestHelpers.swift
//  JunkOSTests
//
//  Helper functions and custom assertions for testing
//

import XCTest
@testable import JunkOS

// MARK: - Custom Assertions

/// Assert that an address is valid (has street, city, and zip)
func XCTAssertAddressValid(_ address: Address, file: StaticString = #filePath, line: UInt = #line) {
    XCTAssertFalse(address.street.isEmpty, "Address street should not be empty", file: file, line: line)
    XCTAssertFalse(address.city.isEmpty, "Address city should not be empty", file: file, line: line)
    XCTAssertFalse(address.zipCode.isEmpty, "Address zipCode should not be empty", file: file, line: line)
}

/// Assert that an address is invalid
func XCTAssertAddressInvalid(_ address: Address, file: StaticString = #filePath, line: UInt = #line) {
    let isValid = !address.street.isEmpty && !address.city.isEmpty && !address.zipCode.isEmpty
    XCTAssertFalse(isValid, "Address should be invalid", file: file, line: line)
}

/// Assert that a BookingData object is complete and ready for submission
func XCTAssertBookingComplete(_ booking: BookingData, file: StaticString = #filePath, line: UInt = #line) {
    XCTAssertTrue(booking.isAddressValid, "Booking address should be valid", file: file, line: line)
    XCTAssertTrue(booking.hasSelectedServices, "Booking should have selected services", file: file, line: line)
    XCTAssertTrue(booking.hasSelectedDateTime, "Booking should have selected date and time", file: file, line: line)
}

/// Assert that a BookingData object is incomplete
func XCTAssertBookingIncomplete(_ booking: BookingData, file: StaticString = #filePath, line: UInt = #line) {
    let isComplete = booking.isAddressValid && booking.hasSelectedServices && booking.hasSelectedDateTime
    XCTAssertFalse(isComplete, "Booking should be incomplete", file: file, line: line)
}

// MARK: - Async Testing Helpers

/// Wait for a published value to change
func waitForPublishedValue<T: Equatable>(
    _ value: @autoclosure () -> T,
    toEqual expectedValue: T,
    timeout: TimeInterval = 2.0,
    file: StaticString = #filePath,
    line: UInt = #line
) async throws {
    let startTime = Date()
    
    while value() != expectedValue {
        if Date().timeIntervalSince(startTime) > timeout {
            XCTFail("Timeout waiting for value to equal \(expectedValue), got \(value())", file: file, line: line)
            return
        }
        try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
    }
}

/// Wait for a condition to become true
func waitForCondition(
    timeout: TimeInterval = 2.0,
    file: StaticString = #filePath,
    line: UInt = #line,
    condition: () -> Bool
) async throws {
    let startTime = Date()
    
    while !condition() {
        if Date().timeIntervalSince(startTime) > timeout {
            XCTFail("Timeout waiting for condition to become true", file: file, line: line)
            return
        }
        try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
    }
}

// MARK: - Test Data Helpers

extension BookingData {
    /// Create a test booking with default valid values
    static func testBooking() -> BookingData {
        return TestFixtures.completeBooking
    }
    
    /// Create an empty test booking
    static func emptyBooking() -> BookingData {
        return BookingData()
    }
}

// MARK: - Date Helpers

extension Date {
    /// Check if date is in the future
    var isFuture: Bool {
        return self > Date()
    }
    
    /// Check if date is today
    var isToday: Bool {
        return Calendar.current.isDateInToday(self)
    }
}
