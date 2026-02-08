//
//  ServiceSelectionViewModelTests.swift
//  JunkOSTests
//
//  Unit tests for ServiceSelectionViewModel
//

import XCTest
@testable import JunkOS

@MainActor
final class ServiceSelectionViewModelTests: XCTestCase {
    
    var viewModel: ServiceSelectionViewModel!
    
    override func setUp() {
        super.setUp()
        viewModel = ServiceSelectionViewModel()
    }
    
    override func tearDown() {
        viewModel = nil
        super.tearDown()
    }
    
    // MARK: - Initialization Tests
    
    func testInitialization() {
        // Then
        XCTAssertNotNil(viewModel)
        XCTAssertTrue(viewModel.selectedServices.isEmpty)
        XCTAssertEqual(viewModel.serviceDetails, "")
        XCTAssertFalse(viewModel.hasSelectedServices)
    }
    
    func testAvailableServicesNotEmpty() {
        // Then
        XCTAssertFalse(viewModel.availableServices.isEmpty)
        XCTAssertEqual(viewModel.availableServices.count, Service.all.count)
    }
    
    // MARK: - Service Selection Tests
    
    func testToggleServiceSelection() {
        // Given
        let serviceId = "furniture"
        XCTAssertFalse(viewModel.isSelected(serviceId))
        
        // When
        viewModel.toggleService(serviceId)
        
        // Then
        XCTAssertTrue(viewModel.isSelected(serviceId))
        XCTAssertTrue(viewModel.selectedServices.contains(serviceId))
        XCTAssertTrue(viewModel.hasSelectedServices)
    }
    
    func testToggleServiceDeselection() {
        // Given
        let serviceId = "appliances"
        viewModel.toggleService(serviceId)
        XCTAssertTrue(viewModel.isSelected(serviceId))
        
        // When - toggle again to deselect
        viewModel.toggleService(serviceId)
        
        // Then
        XCTAssertFalse(viewModel.isSelected(serviceId))
        XCTAssertFalse(viewModel.selectedServices.contains(serviceId))
        XCTAssertFalse(viewModel.hasSelectedServices)
    }
    
    func testMultipleServiceSelection() {
        // Given
        let service1 = "furniture"
        let service2 = "appliances"
        let service3 = "electronics"
        
        // When
        viewModel.toggleService(service1)
        viewModel.toggleService(service2)
        viewModel.toggleService(service3)
        
        // Then
        XCTAssertEqual(viewModel.selectedServices.count, 3)
        XCTAssertTrue(viewModel.isSelected(service1))
        XCTAssertTrue(viewModel.isSelected(service2))
        XCTAssertTrue(viewModel.isSelected(service3))
        XCTAssertTrue(viewModel.hasSelectedServices)
    }
    
    func testDeselectService() {
        // Given - select three services
        viewModel.toggleService("furniture")
        viewModel.toggleService("appliances")
        viewModel.toggleService("electronics")
        XCTAssertEqual(viewModel.selectedServices.count, 3)
        
        // When - deselect one
        viewModel.toggleService("appliances")
        
        // Then - should have 2 services
        XCTAssertEqual(viewModel.selectedServices.count, 2)
        XCTAssertTrue(viewModel.isSelected("furniture"))
        XCTAssertFalse(viewModel.isSelected("appliances"))
        XCTAssertTrue(viewModel.isSelected("electronics"))
    }
    
    // MARK: - Validation Tests
    
    func testHasSelectedServicesWhenEmpty() {
        // Given - no services selected
        
        // Then
        XCTAssertFalse(viewModel.hasSelectedServices)
    }
    
    func testHasSelectedServicesWhenNotEmpty() {
        // Given
        viewModel.toggleService("furniture")
        
        // Then
        XCTAssertTrue(viewModel.hasSelectedServices)
    }
    
    // MARK: - Service Names Tests
    
    func testGetSelectedServiceNames() {
        // Given
        viewModel.toggleService("furniture")
        viewModel.toggleService("appliances")
        
        // When
        let serviceNames = viewModel.getSelectedServiceNames()
        
        // Then
        XCTAssertEqual(serviceNames.count, 2)
        XCTAssertTrue(serviceNames.contains("Furniture Removal"))
        XCTAssertTrue(serviceNames.contains("Appliances"))
    }
    
    func testGetSelectedServiceNamesEmpty() {
        // Given - no services selected
        
        // When
        let serviceNames = viewModel.getSelectedServiceNames()
        
        // Then
        XCTAssertTrue(serviceNames.isEmpty)
    }
    
    // MARK: - Service Query Tests
    
    func testIsSelectedForUnselectedService() {
        // Given
        let serviceId = "construction"
        
        // Then
        XCTAssertFalse(viewModel.isSelected(serviceId))
    }
    
    func testIsSelectedForSelectedService() {
        // Given
        let serviceId = "yard"
        viewModel.toggleService(serviceId)
        
        // Then
        XCTAssertTrue(viewModel.isSelected(serviceId))
    }
}
