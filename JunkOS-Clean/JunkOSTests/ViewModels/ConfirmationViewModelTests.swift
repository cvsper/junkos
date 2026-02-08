//
//  ConfirmationViewModelTests.swift
//  JunkOSTests
//
//  Unit tests for ConfirmationViewModel
//

import XCTest
@testable import JunkOS

@MainActor
final class ConfirmationViewModelTests: XCTestCase {
    
    var viewModel: ConfirmationViewModel!
    
    override func setUp() {
        super.setUp()
        viewModel = ConfirmationViewModel()
    }
    
    override func tearDown() {
        viewModel = nil
        super.tearDown()
    }
    
    // MARK: - Initialization Tests
    
    func testInitialization() {
        // Then
        XCTAssertNotNil(viewModel)
        XCTAssertFalse(viewModel.isSubmitting)
        XCTAssertFalse(viewModel.showSuccess)
        XCTAssertFalse(viewModel.elementsVisible)
        XCTAssertEqual(viewModel.celebrationScale, 1.0)
        XCTAssertNotNil(viewModel.priceBreakdown)
    }
    
    // MARK: - Animation Tests
    
    func testStartAnimations() {
        // Given
        XCTAssertFalse(viewModel.elementsVisible)
        
        // When
        viewModel.startAnimations()
        
        // Then
        XCTAssertTrue(viewModel.elementsVisible)
    }
    
    // MARK: - Price Breakdown Tests
    
    func testPriceBreakdownExists() {
        // Then
        XCTAssertNotNil(viewModel.priceBreakdown)
        XCTAssertGreaterThan(viewModel.priceBreakdown.basePrice, 0)
        XCTAssertGreaterThan(viewModel.priceBreakdown.total, 0)
    }
    
    func testPriceBreakdownCalculation() {
        // Given
        let breakdown = viewModel.priceBreakdown
        
        // Then
        let expectedTotal = breakdown.basePrice + breakdown.itemsCharge + breakdown.disposalFee
        XCTAssertEqual(breakdown.total, expectedTotal, accuracy: 0.01)
    }
    
    // MARK: - Submit Booking Tests
    
    func testSubmitBookingStartsSubmitting() {
        // Given
        XCTAssertFalse(viewModel.isSubmitting)
        
        // When
        let expectation = expectation(description: "Submit booking")
        viewModel.submitBooking {
            expectation.fulfill()
        }
        
        // Then - should be submitting immediately
        XCTAssertTrue(viewModel.isSubmitting)
        
        // Wait for completion
        wait(for: [expectation], timeout: 3.0)
    }
    
    func testSubmitBookingCompletesSuccessfully() async {
        // Given
        let expectation = expectation(description: "Submit booking completes")
        
        // When
        viewModel.submitBooking {
            expectation.fulfill()
        }
        
        // Then
        await fulfillment(of: [expectation], timeout: 3.0)
        XCTAssertFalse(viewModel.isSubmitting)
        XCTAssertTrue(viewModel.showSuccess)
    }
    
    func testSubmitBookingCallsCompletion() {
        // Given
        let expectation = expectation(description: "Completion called")
        var completionCalled = false
        
        // When
        viewModel.submitBooking {
            completionCalled = true
            expectation.fulfill()
        }
        
        // Then
        wait(for: [expectation], timeout: 3.0)
        XCTAssertTrue(completionCalled)
    }
    
    func testSubmitBookingResetsCelebrationScale() async {
        // Given
        let expectation = expectation(description: "Submit completes")
        XCTAssertEqual(viewModel.celebrationScale, 1.0)
        
        // When
        viewModel.submitBooking {
            expectation.fulfill()
        }
        
        // Wait for animation to complete
        await fulfillment(of: [expectation], timeout: 3.0)
        
        // Additional wait for scale animation to reset
        try? await Task.sleep(nanoseconds: 400_000_000) // 0.4 seconds
        
        // Then - scale should be back to 1.0 after animations
        XCTAssertEqual(viewModel.celebrationScale, 1.0, accuracy: 0.01)
    }
    
    // MARK: - Format Price Tests
    
    func testFormatPrice() {
        // Given
        let price = 99.99
        
        // When
        let formatted = viewModel.formatPrice(price)
        
        // Then
        XCTAssertEqual(formatted, "99.99")
    }
    
    func testFormatPriceWithZeroDecimal() {
        // Given
        let price = 100.0
        
        // When
        let formatted = viewModel.formatPrice(price)
        
        // Then
        XCTAssertEqual(formatted, "100.00")
    }
    
    func testFormatPriceWithSingleDecimal() {
        // Given
        let price = 89.5
        
        // When
        let formatted = viewModel.formatPrice(price)
        
        // Then
        XCTAssertEqual(formatted, "89.50")
    }
    
    func testFormatPriceRoundsCorrectly() {
        // Given
        let price = 89.996
        
        // When
        let formatted = viewModel.formatPrice(price)
        
        // Then
        XCTAssertEqual(formatted, "90.00")
    }
    
    // MARK: - Get Service Name Tests
    
    func testGetServiceNameForValidId() {
        // Given
        let serviceId = "furniture"
        
        // When
        let serviceName = viewModel.getServiceName(by: serviceId)
        
        // Then
        XCTAssertNotNil(serviceName)
        XCTAssertEqual(serviceName, "Furniture Removal")
    }
    
    func testGetServiceNameForAnotherValidId() {
        // Given
        let serviceId = "appliances"
        
        // When
        let serviceName = viewModel.getServiceName(by: serviceId)
        
        // Then
        XCTAssertNotNil(serviceName)
        XCTAssertEqual(serviceName, "Appliances")
    }
    
    func testGetServiceNameForInvalidId() {
        // Given
        let serviceId = "invalid_service_id"
        
        // When
        let serviceName = viewModel.getServiceName(by: serviceId)
        
        // Then
        XCTAssertNil(serviceName)
    }
    
    func testGetServiceNameForAllServices() {
        // Test all available services can be retrieved
        for service in Service.all {
            // When
            let serviceName = viewModel.getServiceName(by: service.id)
            
            // Then
            XCTAssertNotNil(serviceName, "Should find service name for \(service.id)")
            XCTAssertEqual(serviceName, service.name)
        }
    }
    
    // MARK: - State Management Tests
    
    func testInitialStateIsNotSubmitting() {
        // Then
        XCTAssertFalse(viewModel.isSubmitting)
        XCTAssertFalse(viewModel.showSuccess)
    }
    
    func testMultipleSubmissions() async {
        // Test that submitting multiple times works correctly
        let expectation1 = expectation(description: "First submission")
        let expectation2 = expectation(description: "Second submission")
        
        // First submission
        viewModel.submitBooking {
            expectation1.fulfill()
        }
        await fulfillment(of: [expectation1], timeout: 3.0)
        
        // Reset state
        viewModel.isSubmitting = false
        viewModel.showSuccess = false
        
        // Second submission
        viewModel.submitBooking {
            expectation2.fulfill()
        }
        await fulfillment(of: [expectation2], timeout: 3.0)
        
        // Both should complete successfully
        XCTAssertTrue(true, "Multiple submissions completed")
    }
}
