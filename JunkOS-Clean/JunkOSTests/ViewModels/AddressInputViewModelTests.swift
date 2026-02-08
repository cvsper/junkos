//
//  AddressInputViewModelTests.swift
//  JunkOSTests
//
//  Unit tests for AddressInputViewModel
//

import XCTest
import CoreLocation
@testable import JunkOS

@MainActor
final class AddressInputViewModelTests: XCTestCase {
    
    var viewModel: AddressInputViewModel!
    var mockLocationManager: MockLocationManager!
    
    override func setUp() {
        super.setUp()
        mockLocationManager = MockLocationManager()
        viewModel = AddressInputViewModel(locationManager: mockLocationManager)
    }
    
    override func tearDown() {
        viewModel = nil
        mockLocationManager = nil
        super.tearDown()
    }
    
    // MARK: - Initialization Tests
    
    func testInitialization() {
        XCTAssertNotNil(viewModel)
        XCTAssertFalse(viewModel.elementsVisible)
        XCTAssertFalse(viewModel.isLoadingLocation)
        XCTAssertEqual(viewModel.region.center.latitude, 27.9506, accuracy: 0.01)
        XCTAssertEqual(viewModel.region.center.longitude, -82.4572, accuracy: 0.01)
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
    
    // MARK: - Location Detection Tests
    
    func testDetectLocationSuccess() async {
        // Given
        mockLocationManager.shouldSucceed = true
        let expectation = XCTestExpectation(description: "Location detected")
        
        // When
        viewModel.detectLocation { result in
            // Then
            switch result {
            case .success(let address):
                XCTAssertAddressValid(address)
                XCTAssertEqual(address.street, "123 Test St")
                XCTAssertEqual(address.city, "Tampa")
                XCTAssertEqual(address.zipCode, "33602")
                expectation.fulfill()
            case .failure:
                XCTFail("Expected success, got failure")
            }
        }
        
        await fulfillment(of: [expectation], timeout: 2.0)
        XCTAssertTrue(mockLocationManager.requestLocationCalled)
        XCTAssertTrue(mockLocationManager.reverseGeocodeCalled)
    }
    
    func testDetectLocationFailure() async {
        // Given
        mockLocationManager.shouldSucceed = false
        mockLocationManager.mockError = NSError(domain: "Test", code: -1)
        let expectation = XCTestExpectation(description: "Location failed")
        
        // When
        viewModel.detectLocation { result in
            // Then
            switch result {
            case .success:
                XCTFail("Expected failure, got success")
            case .failure(let error):
                XCTAssertNotNil(error)
                expectation.fulfill()
            }
        }
        
        await fulfillment(of: [expectation], timeout: 2.0)
        XCTAssertTrue(mockLocationManager.reverseGeocodeCalled)
    }
    
    func testDetectLocationUpdatesLoadingState() {
        // Given
        XCTAssertFalse(viewModel.isLoadingLocation)
        
        // When
        viewModel.detectLocation { _ in }
        
        // Then (immediately after call)
        XCTAssertTrue(viewModel.isLoadingLocation)
    }
    
    // MARK: - Address Validation Tests
    
    func testAddressValidationWithValidAddress() {
        // Given
        let address = TestFixtures.validAddress
        
        // When
        let isValid = viewModel.isAddressValid(
            street: address.street,
            city: address.city,
            zipCode: address.zipCode
        )
        
        // Then
        XCTAssertTrue(isValid)
    }
    
    func testAddressValidationWithEmptyStreet() {
        // When
        let isValid = viewModel.isAddressValid(street: "", city: "Tampa", zipCode: "33602")
        
        // Then
        XCTAssertFalse(isValid)
    }
    
    func testAddressValidationWithEmptyCity() {
        // When
        let isValid = viewModel.isAddressValid(street: "123 Main St", city: "", zipCode: "33602")
        
        // Then
        XCTAssertFalse(isValid)
    }
    
    func testAddressValidationWithEmptyZipCode() {
        // When
        let isValid = viewModel.isAddressValid(street: "123 Main St", city: "Tampa", zipCode: "")
        
        // Then
        XCTAssertFalse(isValid)
    }
    
    func testAddressValidationWithAllEmpty() {
        // When
        let isValid = viewModel.isAddressValid(street: "", city: "", zipCode: "")
        
        // Then
        XCTAssertFalse(isValid)
    }
    
    // MARK: - Region Update Tests
    
    func testRegionUpdatesAfterLocationDetection() async {
        // Given
        mockLocationManager.shouldSucceed = true
        let expectation = XCTestExpectation(description: "Region updated")
        let originalRegion = viewModel.region
        
        // When
        viewModel.detectLocation { _ in
            expectation.fulfill()
        }
        
        await fulfillment(of: [expectation], timeout: 2.0)
        
        // Then
        // Region should be updated to mock location
        XCTAssertEqual(viewModel.region.center.latitude, mockLocationManager.mockLocation.coordinate.latitude, accuracy: 0.01)
        XCTAssertEqual(viewModel.region.center.longitude, mockLocationManager.mockLocation.coordinate.longitude, accuracy: 0.01)
    }
}
