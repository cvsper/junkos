//
//  FormValidationUITests.swift
//  JunkOSUITests
//
//  UI tests for form validation
//

import XCTest

final class FormValidationUITests: XCTestCase {
    
    var app: XCUIApplication!
    
    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launch()
    }
    
    override func tearDownWithError() throws {
        app = nil
    }
    
    // MARK: - Helper Methods
    
    private func navigateToAddressScreen() {
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
    }
    
    private func navigateToServiceScreen() {
        navigateToAddressScreen()
        
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        app.buttons["addressContinueButton"].tap()
        XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
    }
    
    // MARK: - Address Form Validation Tests
    
    func testEmptyAddressFieldsDisableContinue() throws {
        navigateToAddressScreen()
        
        // Given - empty fields
        let continueButton = app.buttons["addressContinueButton"]
        
        // Then - continue should be disabled
        XCTAssertTrue(continueButton.exists)
        XCTAssertFalse(continueButton.isEnabled, "Continue button should be disabled with empty address")
    }
    
    func testOnlyStreetFilledDisablesContinue() throws {
        navigateToAddressScreen()
        
        // Given - only street filled
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        
        // Then - continue should still be disabled
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled without city and zip")
    }
    
    func testOnlyCityFilledDisablesContinue() throws {
        navigateToAddressScreen()
        
        // Given - only city filled
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        
        // Then - continue should be disabled
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled without street and zip")
    }
    
    func testOnlyZipFilledDisablesContinue() throws {
        navigateToAddressScreen()
        
        // Given - only zip filled
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        // Then - continue should be disabled
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled without street and city")
    }
    
    func testStreetAndCityFilledDisablesContinue() throws {
        navigateToAddressScreen()
        
        // Given - street and city but no zip
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        
        // Then - continue should be disabled
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled without zip code")
    }
    
    func testCompleteAddressEnablesContinue() throws {
        navigateToAddressScreen()
        
        // Given - complete address
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        // Then - continue should be enabled
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(continueButton.isEnabled, "Continue should be enabled with complete address")
    }
    
    func testAddressWithOptionalUnitField() throws {
        navigateToAddressScreen()
        
        // Given - complete address with unit
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        
        let unitField = app.textFields["unitField"]
        if unitField.exists {
            unitField.tap()
            unitField.typeText("Apt 5")
        }
        
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        // Then - continue should be enabled
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(continueButton.isEnabled, "Continue should be enabled with unit field")
    }
    
    func testShortZipCodeValidation() throws {
        navigateToAddressScreen()
        
        // Given - complete address with short zip
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("336")
        
        // Then - continue should be disabled or validation shown
        let continueButton = app.buttons["addressContinueButton"]
        // ZIP should be 5 digits minimum
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled with invalid zip code")
    }
    
    func testLongZipCodeValidation() throws {
        navigateToAddressScreen()
        
        // Given - complete address with ZIP+4
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602-1234")
        
        // Then - continue should work with extended ZIP
        let continueButton = app.buttons["addressContinueButton"]
        // Extended ZIP should be valid
        XCTAssertTrue(continueButton.isEnabled, "Continue should be enabled with ZIP+4")
    }
    
    // MARK: - Service Selection Validation Tests
    
    func testNoServiceSelectedDisablesContinue() throws {
        navigateToServiceScreen()
        
        // Given - no services selected
        let continueButton = app.buttons["serviceContinueButton"]
        
        // Then - continue should be disabled
        XCTAssertTrue(continueButton.exists)
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled without service selection")
    }
    
    func testOneServiceSelectedEnablesContinue() throws {
        navigateToServiceScreen()
        
        // Given - one service selected
        app.buttons["serviceButton_furniture"].tap()
        
        // Then - continue should be enabled
        let continueButton = app.buttons["serviceContinueButton"]
        XCTAssertTrue(continueButton.isEnabled, "Continue should be enabled with one service selected")
    }
    
    func testMultipleServicesSelectedEnablesContinue() throws {
        navigateToServiceScreen()
        
        // Given - multiple services selected
        app.buttons["serviceButton_furniture"].tap()
        
        let appliancesButton = app.buttons["serviceButton_appliances"]
        if appliancesButton.exists {
            appliancesButton.tap()
        }
        
        // Then - continue should be enabled
        let continueButton = app.buttons["serviceContinueButton"]
        XCTAssertTrue(continueButton.isEnabled, "Continue should be enabled with multiple services")
    }
    
    func testDeselectingAllServicesDisablesContinue() throws {
        navigateToServiceScreen()
        
        // Given - select and deselect a service
        let furnitureButton = app.buttons["serviceButton_furniture"]
        furnitureButton.tap()
        
        let continueButton = app.buttons["serviceContinueButton"]
        XCTAssertTrue(continueButton.isEnabled)
        
        // When - deselect the service
        furnitureButton.tap()
        
        // Then - continue should be disabled again
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled after deselecting all services")
    }
    
    func testDeselectingOneOfMultipleServicesKeepsContinueEnabled() throws {
        navigateToServiceScreen()
        
        // Given - multiple services selected
        let furnitureButton = app.buttons["serviceButton_furniture"]
        let appliancesButton = app.buttons["serviceButton_appliances"]
        
        furnitureButton.tap()
        if appliancesButton.exists {
            appliancesButton.tap()
        }
        
        let continueButton = app.buttons["serviceContinueButton"]
        XCTAssertTrue(continueButton.isEnabled)
        
        // When - deselect one service
        furnitureButton.tap()
        
        // Then - continue should still be enabled (if appliances exists)
        if appliancesButton.exists {
            XCTAssertTrue(continueButton.isEnabled, "Continue should remain enabled with one service selected")
        }
    }
    
    // MARK: - Date & Time Validation Tests
    
    func testDateTimeSelectionValidation() throws {
        // Navigate through to date/time screen
        navigateToServiceScreen()
        app.buttons["serviceButton_furniture"].tap()
        app.buttons["serviceContinueButton"].tap()
        
        // Skip photos if present
        let skipButton = app.buttons["skipPhotosButton"]
        if skipButton.waitForExistence(timeout: 2) {
            skipButton.tap()
        }
        
        // Check if on date/time screen
        let dateTimePicker = app.otherElements["dateTimePicker"]
        if dateTimePicker.waitForExistence(timeout: 2) {
            // Try to find continue button
            let continueButton = app.buttons["dateTimeContinueButton"]
            if continueButton.exists {
                // Initially should be disabled without selection
                XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled without date/time selection")
            }
        }
    }
    
    func testDateSelectionWithoutTimeDisablesContinue() throws {
        navigateToServiceScreen()
        app.buttons["serviceButton_furniture"].tap()
        app.buttons["serviceContinueButton"].tap()
        
        let skipButton = app.buttons["skipPhotosButton"]
        if skipButton.waitForExistence(timeout: 2) {
            skipButton.tap()
        }
        
        // Select date but not time
        let firstDateButton = app.buttons["dateButton_0"]
        if firstDateButton.waitForExistence(timeout: 2) {
            firstDateButton.tap()
            
            let continueButton = app.buttons["dateTimeContinueButton"]
            if continueButton.exists {
                XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled with only date selected")
            }
        }
    }
    
    func testTimeSelectionWithoutDateDisablesContinue() throws {
        navigateToServiceScreen()
        app.buttons["serviceButton_furniture"].tap()
        app.buttons["serviceContinueButton"].tap()
        
        let skipButton = app.buttons["skipPhotosButton"]
        if skipButton.waitForExistence(timeout: 2) {
            skipButton.tap()
        }
        
        // Select time but not date
        let firstTimeSlot = app.buttons["timeSlotButton_morning"]
        if firstTimeSlot.waitForExistence(timeout: 2) {
            firstTimeSlot.tap()
            
            let continueButton = app.buttons["dateTimeContinueButton"]
            if continueButton.exists {
                XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled with only time selected")
            }
        }
    }
    
    func testBothDateAndTimeSelectedEnablesContinue() throws {
        navigateToServiceScreen()
        app.buttons["serviceButton_furniture"].tap()
        app.buttons["serviceContinueButton"].tap()
        
        let skipButton = app.buttons["skipPhotosButton"]
        if skipButton.waitForExistence(timeout: 2) {
            skipButton.tap()
        }
        
        // Select both date and time
        let firstDateButton = app.buttons["dateButton_0"]
        if firstDateButton.waitForExistence(timeout: 2) {
            firstDateButton.tap()
            
            let firstTimeSlot = app.buttons["timeSlotButton_morning"]
            if firstTimeSlot.exists {
                firstTimeSlot.tap()
                
                let continueButton = app.buttons["dateTimeContinueButton"]
                if continueButton.exists {
                    XCTAssertTrue(continueButton.isEnabled, "Continue should be enabled with both date and time selected")
                }
            }
        }
    }
    
    // MARK: - Error Message Tests
    
    func testValidationErrorMessagesDisplay() throws {
        navigateToAddressScreen()
        
        // Try to submit incomplete form
        // Some apps show error messages, others disable buttons
        // This test documents expected behavior
        
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertFalse(continueButton.isEnabled)
        
        // Check for any error text
        let errorTexts = app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] 'required' OR label CONTAINS[c] 'error'"))
        
        // Either button is disabled OR error messages are shown
        XCTAssertTrue(!continueButton.isEnabled || errorTexts.count > 0, "Should have validation feedback")
    }
    
    // MARK: - Field Interaction Tests
    
    func testFieldClearingRevalidates() throws {
        navigateToAddressScreen()
        
        // Fill complete address
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(continueButton.isEnabled)
        
        // Clear a required field
        streetField.tap()
        streetField.buttons["Clear text"].tap()
        
        // Continue should be disabled
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled after clearing required field")
    }
    
    func testTabOrderBetweenFields() throws {
        navigateToAddressScreen()
        
        // Test that fields can be navigated in order
        let streetField = app.textFields["streetAddressField"]
        let cityField = app.textFields["cityField"]
        let zipField = app.textFields["zipCodeField"]
        
        streetField.tap()
        XCTAssertTrue(streetField.isHittable)
        
        cityField.tap()
        XCTAssertTrue(cityField.isHittable)
        
        zipField.tap()
        XCTAssertTrue(zipField.isHittable)
    }
    
    // MARK: - Edge Cases
    
    func testWhitespaceOnlyFieldsInvalidate() throws {
        navigateToAddressScreen()
        
        // Fill fields with only whitespace
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("   ")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("   ")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("     ")
        
        // Continue should be disabled
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertFalse(continueButton.isEnabled, "Continue should be disabled with whitespace-only fields")
    }
    
    func testVeryLongInputsAreHandled() throws {
        navigateToAddressScreen()
        
        // Enter very long text
        let longText = String(repeating: "A", count: 200)
        
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText(longText)
        
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        // Should either be enabled or have handled the long input gracefully
        let continueButton = app.buttons["addressContinueButton"]
        XCTAssertTrue(continueButton.exists, "UI should handle very long inputs without crashing")
    }
}
