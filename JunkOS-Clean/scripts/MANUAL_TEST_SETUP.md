# Manual Test Target Setup for JunkOS

Since automatic project modification requires additional dependencies, here's the manual setup guide.

## Quick Setup (Recommended)

### Step 1: Open Xcode
```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
open JunkOS.xcodeproj
```

### Step 2: Create Unit Test Target

1. In Xcode, select **File > New > Target...**
2. Choose **iOS > Unit Testing Bundle**
3. Click **Next**
4. Configure:
   - **Product Name:** `JunkOSTests`
   - **Team:** Your development team
   - **Target to be Tested:** `JunkOS`
   - **Language:** Swift
5. Click **Finish**
6. When asked "Would you like to add JunkOSTests to the JunkOS scheme?", click **Add**

### Step 3: Configure Unit Test Target

1. Select **JunkOSTests** target in Project Navigator
2. Go to **Build Settings**
3. Search for "Info.plist" and set **Info.plist File** to: `JunkOSTests/Info.plist`
4. Search for "Bundle Identifier" and set to: `com.junkos.app.tests`
5. Go to **Build Phases** tab
6. Expand **Compile Sources**
7. Click **+** and add all `.swift` files from:
   - `JunkOSTests/Mocks/`
   - `JunkOSTests/Utilities/`
   - `JunkOSTests/ViewModels/`

### Step 4: Create UI Test Target

1. Select **File > New > Target...**
2. Choose **iOS > UI Testing Bundle**
3. Click **Next**
4. Configure:
   - **Product Name:** `JunkOSUITests`
   - **Team:** Your development team
   - **Target to be Tested:** `JunkOS`
   - **Language:** Swift
5. Click **Finish**
6. Click **Add** to add to scheme

### Step 5: Configure UI Test Target

1. Select **JunkOSUITests** target in Project Navigator
2. Go to **Build Settings**
3. Set **Info.plist File** to: `JunkOSUITests/Info.plist`
4. Set **Bundle Identifier** to: `com.junkos.app.uitests`
5. Go to **Build Phases** tab
6. Expand **Compile Sources**
7. Click **+** and add all `.swift` files from:
   - `JunkOSUITests/Tests/`

### Step 6: Enable Code Coverage

1. Select **Product > Scheme > Edit Scheme...**
2. Select **Test** in the left sidebar
3. Go to **Options** tab
4. Check **Code Coverage**
5. Click **Close**

### Step 7: Build and Test

```bash
# Build the project
xcodebuild -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' build

# Run unit tests
xcodebuild test -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:JunkOSTests

# Run UI tests
xcodebuild test -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:JunkOSUITests
```

## Alternative: Script-Based Setup

If you have the xcodeproj gem installed:

```bash
# Install the gem (if not already installed)
gem install xcodeproj

# Run the setup script
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
./scripts/add-test-targets.sh
```

## Verification

After setup, verify everything works:

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean

# List available schemes
xcodebuild -list

# Build with tests
xcodebuild build-for-testing \
  -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15'

# Run all tests
xcodebuild test \
  -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15'
```

Expected output should show:
- JunkOSTests target building successfully
- JunkOSUITests target building successfully
- Tests running (some may be pending implementation)

## Troubleshooting

### "No such module 'JunkOS'"
- Make sure the main app target builds successfully first
- Check that test targets have the main target as a dependency

### "Missing required module 'XCTest'"
- Ensure test targets are properly configured as test bundles
- Check that the SDK is set to iOS Simulator

### Files not compiling
- Verify all `.swift` files are added to **Compile Sources** in Build Phases
- Check that `@testable import JunkOS` is present in test files

### Tests not discoverable
- Make sure test classes inherit from `XCTestCase`
- Test methods must start with `test`
- Mark test classes as `final`

## Quick Test Commands

```bash
# Run a specific test class
xcodebuild test -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  -only-testing:JunkOSTests/AddressInputViewModelTests

# Run a specific test method
xcodebuild test -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  -only-testing:JunkOSTests/AddressInputViewModelTests/testInitialization

# Generate code coverage report
xcodebuild test -scheme JunkOS \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  -enableCodeCoverage YES \
  -resultBundlePath ./test-results
```

## Next Steps

Once setup is complete:

1. ✅ Build the project to ensure it compiles
2. ✅ Run unit tests to verify the infrastructure works
3. 📝 Complete the TODO tests in ViewModel test files
4. 📝 Implement actual assertions in UI tests
5. 📊 Check code coverage and aim for 80%+ on ViewModels

---

**Setup Time:** ~10 minutes  
**Difficulty:** Easy (mostly clicking in Xcode)
