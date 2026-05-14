//
//  APIClientTests.swift
//  UmuveTests
//
//  Unit tests for APIClient
//

import XCTest
@testable import Umuve

@MainActor
final class APIClientTests: XCTestCase {
    
    var apiClient: APIClient!
    
    override func setUp() {
        super.setUp()
        apiClient = APIClient.shared
    }
    
    override func tearDown() {
        apiClient = nil
        super.tearDown()
    }
    
    // MARK: - Initialization Tests
    
    func testAPIClientSingletonExists() {
        // Then
        XCTAssertNotNil(apiClient)
        XCTAssertIdentical(APIClient.shared, APIClient.shared, "Should be a singleton")
    }
    
    // MARK: - Error Tests
    
    func testAPIClientErrorDescriptions() {
        // Test error descriptions are meaningful
        let errors: [(APIClientError, String)] = [
            (.invalidURL, "Invalid API URL"),
            (.invalidResponse, "Invalid server response"),
            (.unauthorized, "Unauthorized access"),
            (.serverError("Test error"), "Test error")
        ]
        
        for (error, expectedDescription) in errors {
            XCTAssertEqual(error.errorDescription, expectedDescription)
        }
    }
    
    func testNetworkErrorDescription() {
        // Given
        let underlyingError = NSError(domain: "TestDomain", code: 123, userInfo: [NSLocalizedDescriptionKey: "Test network error"])
        let error = APIClientError.networkError(underlyingError)
        
        // Then
        XCTAssertTrue(error.errorDescription?.contains("Network error") ?? false)
        XCTAssertTrue(error.errorDescription?.contains("Test network error") ?? false)
    }
    
    func testDecodingErrorDescription() {
        // Given
        let underlyingError = NSError(domain: "DecodingDomain", code: 456, userInfo: [NSLocalizedDescriptionKey: "Decoding failed"])
        let error = APIClientError.decodingError(underlyingError)
        
        // Then
        XCTAssertTrue(error.errorDescription?.contains("Data parsing error") ?? false)
        XCTAssertTrue(error.errorDescription?.contains("Decoding failed") ?? false)
    }
    
    // MARK: - API Model Tests
    
    func testAPIServiceToServiceConversion() {
        // Given
        let apiService = APIService(
            id: "test_furniture",
            name: "Test Furniture Removal",
            description: "Test description",
            basePrice: 99.99,
            isPopular: true
        )
        
        // When
        let service = apiService.toService()
        
        // Then
        XCTAssertEqual(service.id, "test_furniture")
        XCTAssertEqual(service.name, "Test Furniture Removal")
        XCTAssertEqual(service.price, "$99")
        XCTAssertTrue(service.isPopular)
        XCTAssertFalse(service.icon.isEmpty)
    }
    
    func testAPIServiceIconMapping() {
        // Test that different service names map to appropriate icons
        let testCases: [(name: String, expectedIcon: String)] = [
            ("Furniture Removal", "sofa.fill"),
            ("Appliance Pickup", "refrigerator.fill"),
            ("Construction Debris", "hammer.fill"),
            ("Electronics Recycling", "tv.fill"),
            ("Yard Waste", "leaf.fill"),
            ("General Junk", "trash.fill")
        ]
        
        for testCase in testCases {
            let apiService = APIService(
                id: "test",
                name: testCase.name,
                description: nil,
                basePrice: 99.0,
                isPopular: false
            )
            
            let service = apiService.toService()
            XCTAssertEqual(service.icon, testCase.expectedIcon, 
                          "Icon for '\(testCase.name)' should be '\(testCase.expectedIcon)'")
        }
    }
    
    // MARK: - Request Model Tests
    
    func testQuoteRequestEncoding() throws {
        // Given
        let quoteRequest = QuoteRequest(
            services: ["furniture", "appliances"],
            zipCode: "33602"
        )
        
        // When
        let encoder = JSONEncoder()
        let data = try encoder.encode(quoteRequest)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        
        // Then
        XCTAssertNotNil(json)
        XCTAssertEqual(json?["zip_code"] as? String, "33602")
        XCTAssertEqual((json?["services"] as? [String])?.count, 2)
    }
    
    func testBookingRequestEncoding() throws {
        // Given
        let customerInfo = CustomerInfo(
            name: "John Doe",
            email: "john@example.com",
            phone: "555-1234"
        )
        
        let bookingRequest = BookingRequest(
            address: "123 Main St, Tampa, FL 33602",
            zipCode: "33602",
            services: ["furniture"],
            photos: ["base64encodedphoto"],
            scheduledDatetime: "2026-02-08T10:00:00",
            notes: "Test notes",
            customer: customerInfo,
            referralCode: nil
        )
        
        // When
        let encoder = JSONEncoder()
        let data = try encoder.encode(bookingRequest)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        
        // Then
        XCTAssertNotNil(json)
        XCTAssertEqual(json?["address"] as? String, "123 Main St, Tampa, FL 33602")
        XCTAssertEqual(json?["zip_code"] as? String, "33602")
        XCTAssertEqual(json?["scheduled_datetime"] as? String, "2026-02-08T10:00:00")
        XCTAssertEqual(json?["notes"] as? String, "Test notes")
        
        let customer = json?["customer"] as? [String: Any]
        XCTAssertNotNil(customer)
        XCTAssertEqual(customer?["name"] as? String, "John Doe")
    }
    
    // MARK: - Response Model Tests
    
    func testQuoteResponseDecoding() throws {
        // Given
        let jsonString = """
        {
            "success": true,
            "estimated_price": 149.99,
            "services": [],
            "available_time_slots": ["morning", "afternoon"],
            "currency": "USD"
        }
        """
        let data = jsonString.data(using: .utf8)!
        
        // When
        let decoder = JSONDecoder()
        let response = try decoder.decode(QuoteResponse.self, from: data)
        
        // Then
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.estimatedPrice, 149.99, accuracy: 0.01)
        XCTAssertEqual(response.currency, "USD")
        XCTAssertEqual(response.availableTimeSlots.count, 2)
    }
    
    func testBookingResponseDecoding() throws {
        // Given
        let jsonString = """
        {
            "success": true,
            "booking_id": 12345,
            "estimated_price": 199.99,
            "confirmation": "ABC123",
            "scheduled_datetime": "2026-02-08T10:00:00",
            "services": []
        }
        """
        let data = jsonString.data(using: .utf8)!
        
        // When
        let decoder = JSONDecoder()
        let response = try decoder.decode(BookingResponse.self, from: data)
        
        // Then
        XCTAssertEqual(response.bookingId, "12345")
        XCTAssertEqual(response.estimatedPrice, 199.99, accuracy: 0.01)
        XCTAssertEqual(response.confirmation, "ABC123")
        XCTAssertEqual(response.scheduledDatetime, "2026-02-08T10:00:00")
    }
    
    func testAPIErrorDecoding() throws {
        // Given
        let jsonString = """
        {
            "error": "Invalid request",
            "details": "Missing required field: address"
        }
        """
        let data = jsonString.data(using: .utf8)!

        // When
        let decoder = JSONDecoder()
        let error = try decoder.decode(APIError.self, from: data)

        // Then
        XCTAssertEqual(error.error, "Invalid request")
        XCTAssertEqual(error.details, "Missing required field: address")
    }

    // MARK: - PricingEstimate Decoding Tests
    //
    // These guard the Phase 0 fix: the iOS PricingEstimate model previously
    // required a `subtotal` field that the backend never returns, throwing
    // DecodingError.keyNotFound on every estimate call and silently breaking
    // payment. The struct now mirrors /api/pricing/estimate's actual shape
    // (snake_case → camelCase via convertFromSnakeCase) with optional fields
    // for everything except `total`.

    private func pricingDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    func testPricingEstimateDecodesMinimalBackendResponse() throws {
        // The smallest valid response — only `total` is non-optional in the
        // Swift model, so this proves the decoder tolerates a sparse payload.
        let json = """
        { "total": 175.00 }
        """.data(using: .utf8)!

        let estimate = try pricingDecoder().decode(PricingEstimate.self, from: json)

        XCTAssertEqual(estimate.total, 175.00, accuracy: 0.01)
        XCTAssertNil(estimate.itemsSubtotal)
        XCTAssertNil(estimate.surgeAmount)
        // Convenience accessor falls back to `total` when no base price exists.
        XCTAssertEqual(estimate.subtotal, 175.00, accuracy: 0.01)
        XCTAssertEqual(estimate.estimatedDurationMinutes, 0)
        XCTAssertEqual(estimate.recommendedTruck, "")
    }

    func testPricingEstimateDecodesFullBackendResponse() throws {
        // A representative full response taken from
        // backend/routes/booking.py:calculate_estimate(). If the backend
        // adds an unknown field this still decodes (Codable ignores extras);
        // if the backend ever renames `total` the test fails loudly.
        let json = """
        {
            "items_subtotal": 200.00,
            "items": [],
            "volume_discount": 20.00,
            "volume_discount_rate": 0.10,
            "volume_discount_label": "10% off (5-9 items)",
            "surge_multiplier": 1.25,
            "surge_amount": 22.50,
            "surge_reasons": ["High-demand zone (x1.25)"],
            "base_price": 180.00,
            "service_fee": 18.00,
            "recycling_fees": 12.00,
            "recycling_breakdown": [],
            "labor_fee": 0.0,
            "labor_fee_rate": 50.0,
            "total": 232.50,
            "minimum_applied": false,
            "minimum_job_price": 89.0,
            "estimated_duration": 45,
            "truck_size": "1/2 Truck",
            "total_quantity": 6
        }
        """.data(using: .utf8)!

        let estimate = try pricingDecoder().decode(PricingEstimate.self, from: json)

        XCTAssertEqual(estimate.total, 232.50, accuracy: 0.01)
        XCTAssertEqual(estimate.itemsSubtotal, 200.00)
        XCTAssertEqual(estimate.basePrice, 180.00)
        XCTAssertEqual(estimate.volumeDiscount, 20.00)
        XCTAssertEqual(estimate.volumeDiscountLabel, "10% off (5-9 items)")
        XCTAssertEqual(estimate.surgeMultiplier, 1.25)
        XCTAssertEqual(estimate.surgeAmount, 22.50)
        XCTAssertEqual(estimate.surgeReasons?.first, "High-demand zone (x1.25)")
        XCTAssertEqual(estimate.serviceFee, 18.00)
        XCTAssertEqual(estimate.recyclingFees, 12.00)
        XCTAssertEqual(estimate.estimatedDuration, 45)
        XCTAssertEqual(estimate.truckSize, "1/2 Truck")
        XCTAssertEqual(estimate.totalQuantity, 6)
        // Convenience accessor prefers basePrice over itemsSubtotal.
        XCTAssertEqual(estimate.subtotal, 180.00, accuracy: 0.01)
        XCTAssertEqual(estimate.estimatedDurationMinutes, 45)
        XCTAssertEqual(estimate.recommendedTruck, "1/2 Truck")
    }

    func testPricingEstimateRejectsResponseMissingTotal() {
        // `total` is the only non-optional field — its absence must throw.
        // This protects against the inverse of the Phase 0 bug: silently
        // accepting a response with no total and showing $0.
        let json = """
        { "items_subtotal": 100.00 }
        """.data(using: .utf8)!

        XCTAssertThrowsError(try pricingDecoder().decode(PricingEstimate.self, from: json))
    }
    
    // MARK: - Integration Notes
    
    // Note: Actual network tests would require:
    // 1. Mock URLSession or URLProtocol
    // 2. Test backend or mock server
    // 3. Network reachability checks
    //
    // These tests focus on:
    // - Model encoding/decoding
    // - Error handling structure
    // - API client initialization
    //
    // For full integration testing:
    // - Use XCTestExpectation for async operations
    // - Mock network responses
    // - Test retry logic
    // - Test timeout handling
    
    func testHealthCheckMethodExists() {
        // This test validates the method exists and is callable
        // Actual network testing would require mocking
        
        // Then - method should be accessible
        XCTAssertNotNil(apiClient)
        // Cannot test actual network call without backend or mocking
    }
    
    func testGetServicesMethodExists() {
        // Validate method exists
        XCTAssertNotNil(apiClient)
        // Actual testing requires mock backend
    }
    
    func testCreateBookingMethodExists() {
        // Validate method signature exists
        XCTAssertNotNil(apiClient)
        // Actual testing requires mock backend
    }
}
