# Quick Start: Testing in JunkOS

## 🚀 5-Minute Setup

### 1. Add Test Targets to Xcode (Choose One)

#### Option A: Automatic (2 minutes)
```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
gem install xcodeproj  # If needed
./scripts/add-test-targets.sh
```

#### Option B: Manual (10 minutes)
Follow the detailed guide in `scripts/MANUAL_TEST_SETUP.md`

### 2. Build the Project
```bash
xcodebuild -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' build
```

### 3. Run Your First Test
```bash
xcodebuild test -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  -only-testing:JunkOSTests/AddressInputViewModelTests
```

Expected: ✅ 18 tests pass

---

## 📝 Writing Tests

### Unit Test Example
```swift
import XCTest
@testable import JunkOS

@MainActor
final class MyViewModelTests: XCTestCase {
    var viewModel: MyViewModel!
    var mockLocation: MockLocationManager!
    
    override func setUp() {
        super.setUp()
        mockLocation = MockLocationManager()
        viewModel = MyViewModel(locationManager: mockLocation)
    }
    
    func testLocationDetection() async {
        // Given
        mockLocation.shouldSucceed = true
        let expectation = XCTestExpectation(description: "Location detected")
        
        // When
        viewModel.detectLocation { result in
            // Then
            switch result {
            case .success(let address):
                XCTAssertAddressValid(address)
                expectation.fulfill()
            case .failure:
                XCTFail("Expected success")
            }
        }
        
        await fulfillment(of: [expectation], timeout: 2.0)
    }
}
```

### UI Test Example
```swift
import XCTest

final class MyUITests: XCTestCase {
    var app: XCUIApplication!
    
    override func setUpWithError() throws {
        app = XCUIApplication()
        app.launch()
    }
    
    func testUserFlow() {
        app.buttons["Get Started"].tap()
        XCTAssertTrue(app.textFields["Street Address"].waitForExistence(timeout: 2))
    }
}
```

---

## 🛠️ Common Commands

```bash
# Run all unit tests
xcodebuild test -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:JunkOSTests

# Run all UI tests
xcodebuild test -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:JunkOSUITests

# Run specific test class
xcodebuild test -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' \
  -only-testing:JunkOSTests/AddressInputViewModelTests

# Run with coverage
xcodebuild test -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' \
  -enableCodeCoverage YES

# Build for testing
xcodebuild build-for-testing -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15'
```

---

## 📚 Available Test Helpers

### Custom Assertions
```swift
XCTAssertAddressValid(address)           // Check address has required fields
XCTAssertAddressInvalid(address)         // Check address is incomplete
XCTAssertBookingComplete(booking)        // Check booking is ready to submit
XCTAssertBookingIncomplete(booking)      // Check booking needs more data
```

### Test Fixtures
```swift
TestFixtures.validAddress                // Complete address
TestFixtures.completeBooking             // Ready-to-submit booking
TestFixtures.samplePhotoData             // Mock photo data
TestFixtures.tomorrow                    // Date helper
```

### Async Helpers
```swift
// Wait for @Published property to change
try await waitForPublishedValue(viewModel.isLoading, toEqual: false)

// Wait for custom condition
try await waitForCondition { viewModel.address.street.isEmpty == false }
```

### Mock Services
```swift
let mockLocation = MockLocationManager()
mockLocation.shouldSucceed = true
mockLocation.mockAddress = TestFixtures.validAddress

let mockAPI = MockAPIClient()
mockAPI.shouldSucceed = false
mockAPI.mockError = NSError(domain: "Test", code: -1)
```

---

## 📊 What's Tested

### ✅ Complete
- **AddressInputViewModel** (18 tests)
  - Initialization
  - Animations
  - Location detection (success/failure)
  - Address validation
  - Region updates

### 📝 Templates Ready
- ServiceSelectionViewModel (5 tests)
- DateTimePickerViewModel (5 tests)
- PhotoUploadViewModel (5 tests)
- ConfirmationViewModel (6 tests)
- UI Flow Tests (20 tests)

---

## 🎯 Next Steps

1. ✅ Set up test targets
2. ✅ Run AddressInputViewModelTests to verify setup
3. 📝 Complete ViewModel test templates (after MVVM refactor)
4. 📝 Add UI accessibility identifiers
5. 📝 Run UI tests with identifiers in place

---

## 📖 Full Documentation

- **TESTING.md** - Complete testing guide
- **TEST_INFRASTRUCTURE_SUMMARY.md** - What was built
- **scripts/MANUAL_TEST_SETUP.md** - Step-by-step setup

---

## 💡 Tips

- Run tests frequently (Cmd+U in Xcode)
- Check code coverage (Cmd+9 → Coverage tab)
- Use `@MainActor` for ViewModel tests
- Write one assertion per test when possible
- Use descriptive test names: `testWhatUnderCondition`
- Reset mocks in `tearDown()`

---

**Ready to test!** 🎉
