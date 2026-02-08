# JunkOS Testing Infrastructure

This document describes the testing setup for the JunkOS iOS app.

## Test Targets

### JunkOSTests (Unit Tests)
- **Bundle ID:** `com.junkos.app.tests`
- **Purpose:** Unit tests for ViewModels, Models, and Utilities
- **Framework:** XCTest

### JunkOSUITests (UI Tests)
- **Bundle ID:** `com.junkos.app.uitests`
- **Purpose:** End-to-end UI tests for user flows
- **Framework:** XCTest + XCUITest

## Directory Structure

```
JunkOS-Clean/
├── JunkOSTests/
│   ├── Info.plist
│   ├── Mocks/
│   │   ├── MockLocationManager.swift
│   │   └── MockAPIClient.swift
│   ├── Utilities/
│   │   ├── TestFixtures.swift
│   │   └── TestHelpers.swift
│   └── ViewModels/
│       ├── AddressInputViewModelTests.swift
│       ├── ServiceSelectionViewModelTests.swift
│       ├── DateTimePickerViewModelTests.swift
│       ├── PhotoUploadViewModelTests.swift
│       └── ConfirmationViewModelTests.swift
│
└── JunkOSUITests/
    ├── Info.plist
    └── Tests/
        ├── BookingFlowUITests.swift
        ├── NavigationUITests.swift
        └── FormValidationUITests.swift
```

## What's Included

### ✅ Mock Services
- **MockLocationManager**: Simulates location detection and geocoding
- **MockAPIClient**: Future-ready API client for backend integration

### ✅ Test Utilities
- **TestFixtures**: Sample data (addresses, bookings, services, dates)
- **TestHelpers**: Custom assertions and async testing helpers
  - `XCTAssertAddressValid()` / `XCTAssertAddressInvalid()`
  - `XCTAssertBookingComplete()` / `XCTAssertBookingIncomplete()`
  - `waitForPublishedValue()` - Async wait for @Published changes
  - `waitForCondition()` - General async condition waiter

### ✅ ViewModel Tests
- **AddressInputViewModelTests**: ✅ Complete (18 tests)
  - Initialization
  - Animation triggers
  - Location detection (success/failure)
  - Address validation
  - Region updates
  
- **ServiceSelectionViewModelTests**: 📝 Template (ready for implementation)
- **DateTimePickerViewModelTests**: 📝 Template (ready for implementation)
- **PhotoUploadViewModelTests**: 📝 Template (ready for implementation)
- **ConfirmationViewModelTests**: 📝 Template (ready for implementation)

### ✅ UI Tests
- **BookingFlowUITests**: End-to-end flow testing
  - Complete booking flow test
  - Flow with photos
  - Back navigation
  - Partial flow tests
  
- **NavigationUITests**: Navigation between screens
  - Forward navigation
  - Backward navigation
  - Data preservation
  
- **FormValidationUITests**: Input validation
  - Address form validation
  - Service selection validation
  - Date/time validation
  - Error messages

## Running Tests

### Command Line

```bash
# Run all unit tests
xcodebuild test \
  -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15,OS=17.0' \
  -only-testing:JunkOSTests

# Run all UI tests
xcodebuild test \
  -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15,OS=17.0' \
  -only-testing:JunkOSUITests

# Run specific test
xcodebuild test \
  -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15,OS=17.0' \
  -only-testing:JunkOSTests/AddressInputViewModelTests

# Run with coverage
xcodebuild test \
  -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15,OS=17.0' \
  -enableCodeCoverage YES
```

### Xcode

1. Open `JunkOS.xcodeproj`
2. Select the test target (JunkOSTests or JunkOSUITests)
3. Press `Cmd+U` to run all tests
4. Use the Test Navigator (Cmd+6) to run individual tests

## Code Coverage

Code coverage is enabled for all test runs. To view coverage:

1. Run tests with coverage enabled (Xcode does this by default)
2. Open the Report Navigator (Cmd+9)
3. Select the latest test run
4. Click the "Coverage" tab

**Target Coverage Goals:**
- ViewModels: 80%+
- Models: 90%+
- Utilities: 70%+

## CI/CD Integration

Tests are designed to run in CI environments:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    xcodebuild test \
      -scheme JunkOS \
      -destination 'platform=iOS Simulator,name=iPhone 15' \
      -enableCodeCoverage YES \
      -resultBundlePath ./test-results
```

## Writing New Tests

### Unit Test Template

```swift
import XCTest
@testable import JunkOS

@MainActor
final class MyViewModelTests: XCTestCase {
    
    var viewModel: MyViewModel!
    
    override func setUp() {
        super.setUp()
        viewModel = MyViewModel()
    }
    
    override func tearDown() {
        viewModel = nil
        super.tearDown()
    }
    
    func testSomething() {
        // Given
        
        // When
        
        // Then
        XCTAssert...
    }
}
```

### UI Test Template

```swift
import XCTest

final class MyUITests: XCTestCase {
    
    var app: XCUIApplication!
    
    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launch()
    }
    
    func testUserFlow() throws {
        // Arrange
        
        // Act
        app.buttons["MyButton"].tap()
        
        // Assert
        XCTAssertTrue(app.staticTexts["ExpectedText"].exists)
    }
}
```

## Best Practices

1. **Keep tests isolated**: Each test should be independent
2. **Use fixtures**: Don't create test data inline
3. **Name tests clearly**: `testWhatIsTestedUnderWhatCondition`
4. **Test one thing**: Each test should verify one behavior
5. **Use custom assertions**: Make tests more readable
6. **Mock external dependencies**: Use MockLocationManager, MockAPIClient
7. **Async testing**: Use `await` and `async` properly
8. **Clean up**: Reset mocks in tearDown

## Known Issues / TODOs

- [ ] Complete ViewModel test implementations (templates provided)
- [ ] Add accessibility identifier tests
- [ ] Add performance tests for large data sets
- [ ] Add screenshot tests (optional)
- [ ] Integration tests for full backend flow (when API exists)

## Adding Tests to Xcode Project

The test files have been created but need to be added to the Xcode project file. To add them:

### Option 1: Xcode GUI
1. Open `JunkOS.xcodeproj` in Xcode
2. Right-click on the project navigator
3. Select "Add Files to JunkOS..."
4. Select the test files and choose the appropriate target

### Option 2: Command Line (recommended)
Run the provided script to automatically add all test files to the project:

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
# Script to be created
./scripts/add-tests-to-project.sh
```

---

**Created:** February 7, 2026  
**Last Updated:** February 7, 2026  
**Status:** Infrastructure Complete, Tests Ready for Implementation
