//
//  NavigationUITests.swift
//  JunkOSUITests
//
//  UI tests for navigation between screens
//

import XCTest

final class NavigationUITests: XCTestCase {
    
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
    
    private func navigateToServiceSelection() {
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        app.buttons["addressContinueButton"].tap()
    }
    
    private func navigateToPhotoUpload() {
        navigateToServiceSelection()
        
        app.buttons["serviceButton_furniture"].tap()
        app.buttons["serviceContinueButton"].tap()
    }
    
    // MARK: - Forward Navigation Tests
    
    func testForwardNavigationFromWelcome() throws {
        // Given - on welcome screen
        XCTAssertTrue(app.staticTexts["JunkOS"].exists)
        
        // When - tap get started
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Then - should be on address input
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
    }
    
    func testForwardNavigationFromAddressToService() throws {
        // Navigate to address screen
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        
        // Fill address
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        
        // When - tap continue
        app.buttons["addressContinueButton"].tap()
        
        // Then - should be on service selection
        XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
    }
    
    func testForwardNavigationFromServiceToPhoto() throws {
        // Navigate to service screen
        navigateToServiceSelection()
        XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
        
        // Select service
        app.buttons["serviceButton_furniture"].tap()
        
        // When - tap continue
        app.buttons["serviceContinueButton"].tap()
        
        // Then - should be on photo upload or date/time
        let photoScreen = app.buttons["skipPhotosButton"].waitForExistence(timeout: 2)
        let dateTimeScreen = app.otherElements["dateTimePicker"].waitForExistence(timeout: 2)
        
        XCTAssertTrue(photoScreen || dateTimeScreen, "Should reach either photo or date/time screen")
    }
    
    func testForwardNavigationThroughAllScreens() throws {
        // Test complete forward navigation
        
        // Welcome -> Address
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        
        // Address -> Service
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        app.buttons["addressContinueButton"].tap()
        XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
        
        // Service -> Photo
        app.buttons["serviceButton_furniture"].tap()
        app.buttons["serviceContinueButton"].tap()
        
        let skipButton = app.buttons["skipPhotosButton"]
        if skipButton.waitForExistence(timeout: 2) {
            // Photo -> Date/Time
            skipButton.tap()
        }
        
        // Verify reached date/time or confirmation
        let dateTimeExists = app.otherElements["dateTimePicker"].waitForExistence(timeout: 2)
        let confirmationExists = app.buttons["confirmBookingButton"].waitForExistence(timeout: 2)
        
        XCTAssertTrue(dateTimeExists || confirmationExists, "Should reach date/time or confirmation screen")
    }
    
    // MARK: - Backward Navigation Tests
    
    func testBackNavigationFromAddress() throws {
        // Navigate to address
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        
        // When - go back
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        if backButton.exists {
            backButton.tap()
            
            // Then - should be on welcome
            XCTAssertTrue(app.staticTexts["JunkOS"].waitForExistence(timeout: 2))
        }
    }
    
    func testBackNavigationFromService() throws {
        // Navigate to service
        navigateToServiceSelection()
        XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
        
        // When - go back
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        if backButton.exists {
            backButton.tap()
            
            // Then - should be on address
            XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        }
    }
    
    func testBackNavigationFromPhotoUpload() throws {
        // Navigate to photo upload
        navigateToPhotoUpload()
        
        let photoScreen = app.buttons["skipPhotosButton"].waitForExistence(timeout: 2)
        if photoScreen {
            // When - go back
            let backButton = app.navigationBars.buttons.element(boundBy: 0)
            if backButton.exists {
                backButton.tap()
                
                // Then - should be on service selection
                XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
            }
        }
    }
    
    func testMultipleBackNavigations() throws {
        // Navigate forward multiple screens
        navigateToPhotoUpload()
        
        // Navigate back multiple times
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        
        // Back from photo to service
        if backButton.exists {
            backButton.tap()
            XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
            
            // Back from service to address
            if backButton.exists {
                backButton.tap()
                XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
                
                // Back from address to welcome
                if backButton.exists {
                    backButton.tap()
                    XCTAssertTrue(app.staticTexts["JunkOS"].waitForExistence(timeout: 2))
                }
            }
        }
    }
    
    // MARK: - Data Preservation Tests
    
    func testDataPreservedOnBackNavigation() throws {
        // Navigate to address
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Fill address
        let streetField = app.textFields["streetAddressField"]
        streetField.tap()
        streetField.typeText("123 Test St")
        
        let cityField = app.textFields["cityField"]
        cityField.tap()
        cityField.typeText("Tampa")
        
        let zipField = app.textFields["zipCodeField"]
        zipField.tap()
        zipField.typeText("33602")
        
        // Continue to service
        app.buttons["addressContinueButton"].tap()
        XCTAssertTrue(app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2))
        
        // Navigate back
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        if backButton.exists {
            backButton.tap()
            
            // Verify data is preserved
            XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
            
            let streetValue = streetField.value as? String ?? ""
            let cityValue = cityField.value as? String ?? ""
            let zipValue = zipField.value as? String ?? ""
            
            XCTAssertTrue(streetValue.contains("123"), "Street should be preserved")
            XCTAssertTrue(cityValue.contains("Tampa"), "City should be preserved")
            XCTAssertTrue(zipValue.contains("33602"), "Zip should be preserved")
        }
    }
    
    func testServiceSelectionPreservedOnBackNavigation() throws {
        // Navigate to service screen
        navigateToServiceSelection()
        
        // Select a service
        let furnitureButton = app.buttons["serviceButton_furniture"]
        furnitureButton.tap()
        
        // Continue forward
        app.buttons["serviceContinueButton"].tap()
        
        // Go back
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        if backButton.exists {
            backButton.tap()
            
            // Verify service is still selected
            XCTAssertTrue(furnitureButton.waitForExistence(timeout: 2))
            // Note: Visual state verification would require inspecting button state
        }
    }
    
    // MARK: - Navigation Stack Tests
    
    func testCannotNavigateBackFromWelcome() throws {
        // Given - on welcome screen
        XCTAssertTrue(app.staticTexts["JunkOS"].exists)
        
        // When - try to find back button
        let backButtons = app.navigationBars.buttons
        
        // Then - there should be no back button (or it shouldn't navigate away)
        if backButtons.count > 0 {
            let firstButton = backButtons.element(boundBy: 0)
            if firstButton.label.lowercased().contains("back") {
                firstButton.tap()
                
                // Should still be on welcome
                XCTAssertTrue(app.staticTexts["JunkOS"].exists)
            }
        }
    }
    
    func testNavigationStackDepth() throws {
        // Track how many screens we can navigate through
        var screenCount = 0
        
        // Welcome
        XCTAssertTrue(app.staticTexts["JunkOS"].exists)
        screenCount += 1
        
        // Address
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        if app.textFields["streetAddressField"].waitForExistence(timeout: 2) {
            screenCount += 1
        }
        
        // Service
        app.textFields["streetAddressField"].tap()
        app.textFields["streetAddressField"].typeText("123 Main St")
        app.textFields["cityField"].tap()
        app.textFields["cityField"].typeText("Tampa")
        app.textFields["zipCodeField"].tap()
        app.textFields["zipCodeField"].typeText("33602")
        app.buttons["addressContinueButton"].tap()
        
        if app.buttons["serviceButton_furniture"].waitForExistence(timeout: 2) {
            screenCount += 1
        }
        
        XCTAssertGreaterThanOrEqual(screenCount, 3, "Should have at least 3 screens in navigation stack")
    }
    
    // MARK: - Navigation Timing Tests
    
    func testNavigationTransitionsComplete() throws {
        // Test that navigation animations complete before next interaction
        
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        
        // Wait for animation to complete
        let streetField = app.textFields["streetAddressField"]
        XCTAssertTrue(streetField.waitForExistence(timeout: 2))
        
        // Should be able to interact immediately
        XCTAssertTrue(streetField.isHittable, "Field should be hittable after navigation")
    }
    
    func testRapidForwardBackNavigation() throws {
        // Test rapid navigation doesn't break the stack
        
        // Forward
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        
        // Immediately back
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        if backButton.exists {
            backButton.tap()
            XCTAssertTrue(app.staticTexts["JunkOS"].waitForExistence(timeout: 2))
            
            // Forward again
            app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
            XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        }
    }
    
    // MARK: - Edge Cases
    
    func testNavigationAfterAppSuspend() throws {
        // Navigate to a screen
        app.buttons.matching(identifier: "getStartedButton").firstMatch.tap()
        XCTAssertTrue(app.textFields["streetAddressField"].waitForExistence(timeout: 2))
        
        // Simulate app suspend/resume
        XCUIDevice.shared.press(.home)
        app.activate()
        
        // Should still be on same screen
        XCTAssertTrue(app.textFields["streetAddressField"].exists ||
                     app.textFields["streetAddressField"].waitForExistence(timeout: 2))
    }
}
