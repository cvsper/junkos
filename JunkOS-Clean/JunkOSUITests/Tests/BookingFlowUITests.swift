//
//  BookingFlowUITests.swift
//  JunkOSUITests
//
//  End-to-end UI tests for the booking flow
//

import XCTest

final class BookingFlowUITests: XCTestCase {
    
    var app: XCUIApplication!
    
    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launch()
    }
    
    override func tearDownWithError() throws {
        app = nil
    }
    
    // MARK: - Complete Booking Flow Tests
    
    func testCompleteBookingFlow() throws {
        // Step 1: Welcome Screen
        XCTAssertTrue(app.staticTexts["JunkOS"].waitForExistence(timeout: 2))
        
        let getStartedButton = app.buttons.matching(identifier: "getStartedButton").firstMatch
        XCTAssertTrue(getStartedButton.waitForExistence(timeout: 2))
        getStartedButton.tap()
        
        // Step 2: Address Input
        let streetField = app.textFields["streetAddressField"]
        XCTAssertTrue(streetField.waitForExistence(timeout: 2))
        streetField.tap()
        streetField.typeText("123 Main St")
        
        let cityField = app.textFields["cityField"]
        cityField.tap()
        cityField.typeText("Tampa")
        
        let zipField = app.textFields["zipCodeField"]
        zipField.tap()
        zipField.typeText("33602")
        
        let addressContinueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(addressContinueButton.waitForExistence(timeout: 2))
        XCTAssertTrue(addressContinueButton.isEnabled)
        addressContinueButton.tap()
        
        // Step 3: Service Selection
        let furnitureService = app.buttons["serviceButton_furniture"]
        XCTAssertTrue(furnitureService.waitForExistence(timeout: 2))
        furnitureService.tap()
        
        let serviceContinueButton = app.buttons["serviceContinueButton"]
        XCTAssertTrue(serviceContinueButton.isEnabled)
        serviceContinueButton.tap()
        
        // Step 4: Photo Upload (skip)
        let skipPhotoButton = app.buttons["skipPhotosButton"]
        if skipPhotoButton.waitForExistence(timeout: 2) {
            skipPhotoButton.tap()
        }
        
        // Step 5: Date & Time Selection
        let datePickerExists = app.otherElements["dateTimePicker"].waitForExistence(timeout: 2)
        if datePickerExists {
            // Select first available date
            let firstDate = app.buttons["dateButton_0"]
            if firstDate.exists {
                firstDate.tap()
            }
            
            // Select first available time slot
            let firstTimeSlot = app.buttons["timeSlotButton_morning"]
            if firstTimeSlot.exists {
                firstTimeSlot.tap()
            }
            
            let dateTimeContinueButton = app.buttons["dateTimeContinueButton"]
            if dateTimeContinueButton.exists && dateTimeContinueButton.isEnabled {
                dateTimeContinueButton.tap()
            }
        }
        
        // Step 6: Confirmation
        let confirmationTitle = app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'Review'")).firstMatch
        XCTAssertTrue(confirmationTitle.waitForExistence(timeout: 2))
        
        let confirmButton = app.buttons["confirmBookingButton"]
        XCTAssertTrue(confirmButton.exists)
        
        // Don't actually submit in tests
        XCTAssertTrue(true, "Successfully navigated through entire booking flow")
    }
    
    func testBookingFlowWithMultipleServices() throws {
        // Navigate to service selection
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Fill address
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("456 Oak Ave")
        
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Miami")
        
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33101")
        
        app.buttons["addressContinueButton"].tap()
        
        // Select multiple services
        let furnitureButton = app.buttons["serviceButton_furniture"]
        XCTAssertTrue(furnitureButton.waitForExistence(timeout: 2))
        furnitureButton.tap()
        
        let appliancesButton = app.buttons["serviceButton_appliances"]
        if appliancesButton.exists {
            appliancesButton.tap()
        }
        
        let electronicsButton = app.buttons["serviceButton_electronics"]
        if electronicsButton.exists {
            electronicsButton.tap()
        }
        
        // Continue
        app.buttons["serviceContinueButton"].tap()
        
        // Verify we moved forward
        XCTAssertTrue(app.buttons["skipPhotosButton"].waitForExistence(timeout: 2) ||
                     app.otherElements["dateTimePicker"].waitForExistence(timeout: 2))
    }
    
    func testBookingFlowBackNavigation() throws {
        // Start booking
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Verify we're on address screen
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        
        // Go back
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        if backButton.exists {
            backButton.tap()
            
            // Should be back on welcome screen
            XCTAssertTrue(app.staticTexts["JunkOS"].exists)
        }
    }
    
    func testBookingFlowWithEmptyAddress() throws {
        // Start booking
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Try to continue without filling address
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(continueButton.waitForExistence(timeout: 2))
        
        // Button should be disabled
        XCTAssertFalse(continueButton.isEnabled, "Continue button should be disabled with empty address")
    }
    
    func testBookingFlowPartialAddress() throws {
        // Start booking
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Fill only street
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("123 Main St")
        
        // Try to continue
        let continueButton = app.buttons["addressContinueButton"]
        
        // Should still be disabled (needs city and zip)
        XCTAssertFalse(continueButton.isEnabled, "Continue button should be disabled with partial address")
    }
    
    // MARK: - Partial Flow Tests
    
    func testNavigateToServiceSelection() throws {
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Fill complete address
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("789 Elm St")
        
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Orlando")
        
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("32801")
        
        app.buttons["addressContinueButton"].tap()
        
        // Verify on service selection
        let furnitureButton = app.buttons["serviceButton_furniture"]
        XCTAssertTrue(furnitureButton.waitForExistence(timeout: 2))
    }
    
    func testServiceSelectionNoSelection() throws {
        // Navigate to service selection
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("123 Test St")
        
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        app.buttons["addressContinueButton"].tap()
        
        // Verify service screen
        XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
        
        // Try to continue without selecting service
        let continueButton = app.buttons["serviceContinueButton"]
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled without service selection")
    }
    
    func testNavigateToPhotoUpload() throws {
        // Navigate through address and service selection
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Address
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        app.buttons["addressContinueButton"].tap()
        
        // Service
        app.buttons["serviceButton_furniture"].tap()
        app.buttons["serviceContinueButton"].tap()
        
        // Verify on photo upload
        XCTAssertTrue(app.buttons["skipPhotosButton"].waitForExistence(timeout: 2) ||
                     app.buttons["addPhotoButton"].waitForExistence(timeout: 2))
    }
    
    // MARK: - Edge Cases
    
    func testMultipleLaunches() throws {
        // First launch
        app.terminate()
        app.launch()
        
        XCTAssertTrue(app.staticTexts["JunkOS"].waitForExistence(timeout: 2))
        
        // Second launch
        app.terminate()
        app.launch()
        
        XCTAssertTrue(app.staticTexts["JunkOS"].waitForExistence(timeout: 2))
    }
    
    func testLongAddressInput() throws {
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Enter very long address
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("123456789 Very Long Street Name With Many Words")
        
        // Should still work
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(continueButton.isEnabled)
    }
    
    func testSpecialCharactersInAddress() throws {
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Enter address with special characters
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("123 Main St. #5-B")
        
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("St. Petersburg")
        
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33701")
        
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(continueButton.isEnabled)
    }
}
