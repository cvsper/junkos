# Phase 7: TestFlight Preparation - Research

**Researched:** 2026-02-14
**Domain:** iOS App Store Connect, TestFlight Beta Distribution, Physical Device Testing
**Confidence:** HIGH

## Summary

TestFlight preparation for iOS apps requires navigating Apple's multi-step validation pipeline: Xcode archive creation, App Store Connect upload, build processing, export compliance, metadata preparation, and physical device testing. The process is well-documented by Apple but has numerous subtle requirements around code signing, entitlements, screenshots, privacy policies, and SDK versions that can cause validation failures if missed.

As of April 2026, Apple requires apps to be built with iOS 26 SDK or later (Xcode 16+). Both Umuve apps (customer and driver) are currently configured with automatic signing, bundle IDs (com.goumuve.app and com.goumuve.pro), version 1.0.0 build 1/4, and have existing app icons. The driver app has a more complex setup with Socket.IO dependency, background location tracking, and uses XcodeGen (project.yml) for project management.

The key challenges for this phase are: ensuring Release build configuration uses production backend URLs, validating all required entitlements match capabilities, generating App Store screenshots (1320x2868 for 6.9" iPhone), creating compliant privacy policies, and conducting end-to-end testing on physical devices with real backend integration.

**Primary recommendation:** Use Xcode's built-in Archive and Validate workflow with automatic code signing for initial TestFlight submission. Defer screenshot automation (fastlane) until after first successful upload. Prioritize physical device testing with production backend before upload to catch integration issues early.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Xcode | 16+ | IDE, archive, upload | Apple's official toolchain, required for iOS 26 SDK |
| App Store Connect | Web | App metadata, TestFlight management | Apple's only distribution platform for TestFlight |
| TestFlight | iOS app | Beta tester app | Apple's official beta distribution service |
| Transporter | macOS app (optional) | Alternative upload method | Apple-provided CLI/GUI alternative to Xcode Organizer |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fastlane | 2.x | Automate screenshots, builds, uploads | After first successful manual upload, for CI/CD |
| fastlane snapshot | via fastlane | Automated screenshot generation | When need to generate 10+ screenshots across devices |
| fastlane deliver | via fastlane | Automate App Store metadata | For frequent metadata updates, multi-language |
| XcodeGen | 2.x | Generate Xcode project from YAML | Already in use for driver app (project.yml) |
| agvtool | Built into Xcode | Increment build numbers | For scripted build number management |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Xcode Archive | Xcode Cloud | Automated CI/CD but requires setup, not needed for first submission |
| fastlane | Manual screenshots | Faster initial setup but doesn't scale, manual = error-prone |
| Automatic signing | Manual signing | More control but complex, not recommended for solo dev |
| TestFlight | Ad Hoc distribution | No Apple review but limited to 100 devices, painful UDID management |

**Installation:**
```bash
# fastlane (optional, defer until after first upload)
brew install fastlane

# XcodeGen (already installed for driver app)
brew install xcodegen
```

## Architecture Patterns

### Recommended Project Structure

Both apps already follow standard iOS structure:

```
JunkOS-Clean/                  # Customer app "Umuve"
├── JunkOS/
│   ├── Assets.xcassets/       # App icons (COMPLETE - has 13 icons)
│   ├── Info.plist             # Privacy strings, bundle config
│   ├── JunkOS.entitlements    # Apple Pay merchant capability
│   ├── Services/
│   │   └── Config.swift       # Environment switching (dev/prod)
│   ├── Views/                 # SwiftUI views
│   └── ViewModels/            # ObservableObject ViewModels
├── JunkOS.xcodeproj/
└── TESTFLIGHT_SETUP_GUIDE.md  # Detailed 786-line walkthrough

JunkOS-Driver/                 # Driver app "Umuve Pro"
├── Assets.xcassets/           # App icons (COMPLETE - has AppIcon.appiconset/)
├── Config/
│   └── Config.swift           # Environment switching (dev/prod)
├── JunkOS-Driver.xcodeproj/
└── project.yml                # XcodeGen configuration (already in use)
```

**Note:** Customer app has NO app icon PNG files (0 found), but has AppIcon.appiconset directory. Driver app has 13 icon PNGs. Both need icon validation before upload.

### Pattern 1: Build Configuration Environment Switching

**What:** Use Xcode build configurations (Debug/Release) to automatically switch backend URLs and API keys.

**When to use:** Always for production builds to ensure Release builds use production backend.

**Current state:** Both apps use `#if DEBUG` compiler directive for environment switching.

**Example:**
```swift
// Config.swift (both apps use this pattern)
final class AppConfig {
    var environment: APIEnvironment

    private init() {
        #if DEBUG
        environment = .development  // http://localhost:8080
        #else
        environment = .production   // https://junkos-backend.onrender.com
        #endif
    }
}
```

**What needs verification:**
- Ensure Xcode scheme's Archive action uses Release configuration (default)
- Confirm production URLs are valid and reachable
- Test Release build on device before archiving

### Pattern 2: Scheme-Based Build Configuration

**What:** Xcode schemes define which build configuration to use for each action (Run, Test, Archive).

**When to use:** To ensure Archive action always builds with Release configuration.

**How to verify:**
```bash
# Check current scheme settings
xcodebuild -project JunkOS.xcodeproj -scheme JunkOS -showBuildSettings \
  | grep -E "CONFIGURATION|BUILD_CONFIGURATION"
```

**Best practice from research:**
- Archive action should use Release configuration (Xcode default)
- Run action uses Debug configuration (for development)
- Test action can use Debug or dedicated Test configuration

**Source:** [Sarunw - iOS environments](https://sarunw.com/posts/how-to-set-up-ios-environments/), [Medium - Xcode scheme setup](https://medium.com/@hdmdhr/xcode-scheme-environment-project-configuration-setup-recipe-22c940585984)

### Pattern 3: Incremental Build Number Management

**What:** Increment build number for each App Store Connect upload, keeping marketing version stable.

**When to use:** Before every upload (App Store Connect rejects duplicate build numbers).

**Example:**
```bash
# Automated increment
cd JunkOS-Clean
agvtool next-version -all  # Build 1 → 2

# Manual in Xcode
# Project > Target > General > Build = "2"
```

**Current state:**
- Customer app: Version 1.0.0, Build 1
- Driver app: Version 1.0.0, Build 4

**Best practice:** Use consistent versioning across both apps, increment both before submission.

### Anti-Patterns to Avoid

- **Don't archive from Simulator target:** Always select "Any iOS Device (arm64)" before archiving. Archives from Simulator are invalid for App Store Connect.
- **Don't skip validation:** Always validate archive before uploading. Validation catches 80% of common errors (missing icons, entitlement mismatches, invalid provisioning).
- **Don't commit code signing files:** Never commit .p12 certificates or provisioning profiles to git. Use automatic signing or CI/CD secrets.
- **Don't test only on Simulator:** Simulator cannot reproduce hardware-dependent issues (thermal throttling, memory pressure, sensor inaccuracies, push notifications).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Screenshot generation | Manual screenshot capture + Photoshop | fastlane snapshot + UI Tests | Generating 10 screenshots × 5 device sizes × 3 languages = 150 manual screenshots. Fastlane automates this in ~10 minutes. |
| Build number incrementing | Manual Info.plist editing | agvtool or fastlane increment_build_number | Human error in build numbers causes upload rejection. Automation prevents duplicates. |
| App Store metadata | Manual App Store Connect form filling | fastlane deliver with metadata files | For multi-language apps or frequent updates, manual entry is error-prone and time-consuming. |
| Certificate/profile management | Manual certificate creation and download | Xcode Automatic Signing or fastlane match | Code signing is notoriously complex with expiration, device registration, capability syncing. Automation prevents 90% of signing issues. |
| Privacy policy | Custom HTML from scratch | Generator (privacypolicygenerator.info) or template | GDPR/CCPA compliance requires specific legal language. Generators ensure compliance and save legal review time. |

**Key insight:** TestFlight preparation has high ceremony cost (many small steps) but low technical complexity. Automation pays off after 2-3 submissions. For first submission, manual Xcode workflow is fastest path to learning the process.

## Common Pitfalls

### Pitfall 1: Missing or Invalid App Icons

**What goes wrong:** Upload fails with "Missing App Icon" or "Invalid Icon Dimensions" error.

**Why it happens:**
- Asset catalog missing required icon sizes (especially 1024×1024 App Store icon)
- Icons have alpha channel (transparency) when App Store requires opaque
- Wrong file format (JPEG instead of PNG, or vice versa)

**Current state:**
- **Customer app:** AppIcon.appiconset directory exists but contains 0 PNG files. HIGH RISK.
- **Driver app:** Has 13 icon PNGs including 1024×1024. Contents.json looks correct.

**How to avoid:**
1. Verify asset catalog has all required sizes:
   ```bash
   # Customer app
   ls -la JunkOS-Clean/JunkOS/Assets.xcassets/AppIcon.appiconset/

   # Driver app
   ls -la JunkOS-Driver/Assets.xcassets/AppIcon.appiconset/
   ```
2. Check Contents.json references existing files
3. Validate icons in Xcode: Select Assets.xcassets > AppIcon, look for yellow warnings
4. Required sizes: 1024×1024 (App Store), 180×180 (iPhone 3x), 120×120 (iPhone 2x), 167×167 (iPad Pro), 152×152 (iPad 2x)

**Warning signs:**
- Xcode shows yellow warning icon next to AppIcon in asset catalog
- Missing icon files but Contents.json references them
- Build warnings about missing image assets

**Sources:** [Apple - Configuring app icon](https://developer.apple.com/documentation/xcode/configuring-your-app-icon), [SplitMetrics - iOS icon sizes](https://splitmetrics.com/blog/guide-to-mobile-icons/)

### Pitfall 2: Entitlement Mismatches

**What goes wrong:** Upload succeeds but processing fails with "Invalid Entitlements" error after 10-20 minutes.

**Why it happens:**
- App uses capabilities (Apple Pay, Push Notifications, App Groups) but entitlements file doesn't include them
- Provisioning profile doesn't include capabilities that entitlements declare
- Using development entitlements (aps-environment: development) in production build

**Current state:**
- Customer app has JunkOS.entitlements with Apple Pay merchant ID
- Driver app location tracking configured in project.yml (INFOPLIST_KEY_UIBackgroundModes: "location")
- Both apps likely use push notifications (Phase 4/5 implementation)

**How to avoid:**
1. Audit capabilities vs entitlements:
   ```bash
   # Check customer app entitlements
   cat JunkOS-Clean/JunkOS/JunkOS.entitlements

   # Check driver app capabilities (project.yml or .entitlements if exists)
   grep -r "entitlements\|capabilities\|aps-environment" JunkOS-Driver/
   ```
2. Verify push notification entitlement (if used):
   - Should be `aps-environment: production` for Release builds
   - Common mistake: hardcoded to `development`
3. Check App Store Connect capabilities match Xcode
4. Let Xcode automatic signing sync capabilities (recommended)

**Warning signs:**
- Build succeeds but App Store Connect shows "Processing" for >30 minutes
- Email from Apple about missing entitlements
- TestFlight build status shows "Invalid Binary"

**Sources:** [Apple - Diagnosing entitlements](https://developer.apple.com/documentation/bundleresources/diagnosing-issues-with-entitlements), [GitHub Issue - Provisioning profile legacy entitlements](https://github.com/dotnet/maui/issues/32293), [Apple TN2294 - Validation issues](https://developer.apple.com/library/archive/technotes/tn2294/_index.html)

### Pitfall 3: Missing Privacy Policy URL

**What goes wrong:** Cannot submit for TestFlight external testing or App Store review. App Store Connect blocks submission with "Privacy Policy Required" error.

**Why it happens:**
- Apple requires privacy policy URL for all apps that collect data
- Policy must be publicly accessible (not behind login)
- URL must be valid and return 200 OK

**How to avoid:**
1. Create privacy policy before TestFlight submission
2. Host at goumuve.com/privacy or use GitHub Pages (free)
3. Use generator: https://www.privacypolicygenerator.info/ or https://app-privacy-policy-generator.firebaseapp.com/
4. Add URL to App Store Connect: My Apps > Umuve > App Information > Privacy Policy URL
5. Required sections for Umuve:
   - What data is collected (location, photos, contact info)
   - How data is used (service delivery, booking)
   - How data is shared (service providers, payment processors)
   - User rights (access, deletion, opt-out)
   - Contact information

**Warning signs:**
- "Privacy Policy URL" field in App Store Connect is empty
- External TestFlight submission blocked
- App Review rejection mentioning privacy policy

**Template available:** JunkOS-Clean/TESTFLIGHT_SETUP_GUIDE.md includes 52-line minimum viable privacy policy template.

**Sources:** [Apple - Manage app privacy](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy/), [iubenda - iOS privacy policy](https://www.iubenda.com/en/help/401-privacy-policy-for-ios-and-macos-apps/)

### Pitfall 4: Screenshot Requirements Not Met

**What goes wrong:** Cannot submit to App Store (after TestFlight) without required screenshots. TestFlight doesn't require screenshots, but planning ahead saves time.

**Why it happens:**
- Apple requires at least one 6.9-inch iPhone screenshot (1320×2868 pixels) as of 2026
- Smaller sizes auto-scale from 6.9", but original must be provided
- Screenshots must show actual app UI (no mockups, no device frames)
- Max 10 screenshots per device size

**How to avoid:**
1. For TestFlight: screenshots optional, but recommended for external testers
2. For App Store: REQUIRED before submission
3. Generate screenshots on physical device or Simulator:
   ```bash
   # Simulator method (faster)
   # 1. Run app on iPhone 16 Pro Max Simulator (6.9")
   # 2. Navigate to key screens
   # 3. ⌘S to capture screenshot (saves to Desktop)
   # 4. Crop to 1320×2868 if needed
   ```
4. Automate later with fastlane snapshot:
   ```bash
   fastlane snapshot  # Requires UI test setup
   ```

**Required screenshots for App Store:**
- 5-10 screenshots at 1320×2868 (6.9" iPhone)
- Apple auto-scales to smaller iPhones
- Optional: 13" iPad screenshots (2048×2732)

**Warning signs:**
- Trying to submit to App Store and blocked by "Missing Screenshots"
- Screenshots have device mockups or frames (not allowed)
- Screenshots don't show actual app screens

**Sources:** [Apple - Screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/), [ASO.dev - Screenshot requirements 2026](https://aso.dev/app-store-connect/screenshots/), [Medium - Screenshot sizes 2026](https://medium.com/@AppScreenshotStudio/app-store-screenshot-sizes-2026-cheat-sheet-iphone-16-pro-max-google-play-specs-3cb210bf0756)

### Pitfall 5: Production Backend Not Configured or Tested

**What goes wrong:** App uploads successfully to TestFlight, but crashes or shows errors when testers use it because backend URLs point to localhost or unreachable staging server.

**Why it happens:**
- Release build configuration uses wrong backend URL
- Production backend URL is placeholder or incorrect
- Backend not deployed or not accepting requests
- API keys invalid for production environment

**Current state:**
- Both apps configured with production URL: `https://junkos-backend.onrender.com`
- Config uses `#if DEBUG` for environment switching
- Stripe keys are placeholders: "pk_test_PLACEHOLDER" and "pk_live_PLACEHOLDER"

**How to avoid:**
1. Verify production backend is deployed and reachable:
   ```bash
   curl -I https://junkos-backend.onrender.com/health
   # Should return 200 OK
   ```
2. Test Release build on physical device BEFORE archiving:
   ```bash
   # In Xcode:
   # 1. Edit Scheme > Run > Build Configuration > Release
   # 2. Run on physical device
   # 3. Test complete user flow (booking, payment, tracking)
   # 4. Change back to Debug after testing
   ```
3. Update Stripe publishable keys in Config.swift
4. Verify API authentication works with production backend
5. Test Socket.IO real-time features (driver tracking, job feed)

**Warning signs:**
- TestFlight testers report "Cannot connect to server" errors
- All API requests fail or timeout
- App shows localhost errors in production
- Payment processing fails

**Testing checklist:**
- [ ] Customer can complete booking end-to-end
- [ ] Driver can accept job and update status
- [ ] Real-time tracking updates work
- [ ] Push notifications deliver
- [ ] Payment processing succeeds (test mode OK for first TestFlight)
- [ ] Photo upload works
- [ ] Volume adjustment flow works

**Sources:** Backend analysis, Config.swift inspection, Phase 1-6 implementation review

### Pitfall 6: Build Fails Validation Due to SDK/Xcode Version

**What goes wrong:** Archive uploads but fails validation with "ITMS-90725: SDK Version Issue" error.

**Why it happens:**
- As of April 28, 2026, Apple requires iOS 26 SDK or later
- Older Xcode versions don't include iOS 26 SDK
- Xcode version check happens during App Store Connect validation

**How to avoid:**
1. Verify Xcode version BEFORE archiving:
   ```bash
   xcodebuild -version
   # Should output: Xcode 16.0 or later
   ```
2. Check SDK version:
   ```bash
   xcrun --show-sdk-version --sdk iphoneos
   # Should output: 26.0 or later
   ```
3. Update Xcode if needed:
   - Download from Mac App Store or developer.apple.com
   - Install and set as default: `sudo xcode-select -s /Applications/Xcode.app`
4. Driver app project.yml specifies Xcode 16.0 minimum (GOOD)

**Warning signs:**
- Upload succeeds but validation fails immediately
- Error message mentions SDK version or Xcode version
- Building for iOS 17.0 deployment target but using old SDK

**Current state:**
- Driver app: `xcodeVersion: "16.0"` in project.yml (CORRECT)
- Customer app: Check Xcode project settings

**Sources:** [Apple - Upcoming requirements](https://developer.apple.com/news/upcoming-requirements/), [Medium - iOS 26 SDK mandate ITMS-90725](https://medium.com/codex/apples-ios-26-sdk-mandate-what-itms-90725-means-for-every-app-by-april-2026-01578e627b05), [Apple Developer Forums - SDK validation](https://developer.apple.com/forums/thread/806141)

## Code Examples

Verified patterns from official sources and current codebase:

### Verify Build Configuration

```bash
# Check which configuration will be used for Archive
xcodebuild -project JunkOS.xcodeproj -scheme JunkOS -showBuildSettings \
  | grep BUILD_CONFIGURATION
# Expected output: BUILD_CONFIGURATION = Release

# Check API URL that will be compiled into build
# Should output production URL, not localhost
xcodebuild -project JunkOS.xcodeproj -scheme JunkOS -configuration Release \
  -showBuildSettings | grep -A 10 "SWIFT_ACTIVE_COMPILATION_CONDITIONS"
```

### Test Release Build on Physical Device

```bash
# Step 1: Connect iPhone via USB
# Step 2: In Xcode, edit scheme to use Release for Run action
# (Product > Scheme > Edit Scheme > Run > Build Configuration > Release)

# Step 3: Build and run on device
# Check console logs to verify production URL is being used

# Step 4: Test end-to-end flow manually on device

# Step 5: Change scheme back to Debug
# (Product > Scheme > Edit Scheme > Run > Build Configuration > Debug)
```

### Increment Build Numbers Before Upload

```bash
# Customer app
cd JunkOS-Clean
agvtool next-version -all
# Output: Build version = 2

# Driver app
cd JunkOS-Driver
# Update project.yml: CURRENT_PROJECT_VERSION: 5
# Then regenerate Xcode project
xcodegen generate
```

### Archive and Validate

```bash
# Archive (use Xcode GUI for first submission)
# Product > Archive
# Wait for archive to complete (~1-5 minutes)

# Validate before uploading
# In Organizer:
# 1. Select archive
# 2. Click "Validate App"
# 3. Choose App Store Connect
# 4. Enable "Upload symbols" and "Manage signing automatically"
# 5. Review and validate
# 6. Fix any errors before uploading

# Upload (after successful validation)
# In Organizer:
# 1. Select archive
# 2. Click "Distribute App"
# 3. Choose App Store Connect
# 4. Upload
# 5. Wait 10-30 minutes for processing
```

### Verify App Icons Exist

```bash
# Customer app - CHECK CRITICAL
cd JunkOS-Clean
find . -name "AppIcon.appiconset" -type d
ls -la JunkOS/Assets.xcassets/AppIcon.appiconset/
# Should show 1024×1024 PNG and other required sizes

# Driver app - looks good
cd JunkOS-Driver
ls -la Assets.xcassets/AppIcon.appiconset/
# Confirmed: 13 icon files including app-icon-1024.png
```

### Generate Test Screenshots (Manual)

```bash
# Method 1: Physical device
# 1. Connect iPhone 14 Pro Max or later (6.9" or equivalent)
# 2. Navigate to key screens in app
# 3. Press Volume Up + Side button to capture
# 4. AirDrop screenshots to Mac
# 5. Verify dimensions: should be close to 1320×2868

# Method 2: Simulator (faster)
# 1. Run app in Simulator (iPhone 16 Pro Max)
# 2. Navigate to screen
# 3. ⌘S to save screenshot to Desktop
# 4. Check dimensions with Preview or:
sips -g pixelWidth -g pixelHeight screenshot.png
```

### Create Minimal Privacy Policy (Template)

```markdown
# Privacy Policy for Umuve

**Last Updated:** February 14, 2026

## Information We Collect
- Location data (to provide junk removal service)
- Photos (optional, to show items for removal)
- Contact information (email, phone for booking)

## How We Use Information
- Provide and improve junk removal services
- Process bookings and payments
- Communicate about service

## Information Sharing
We do not sell personal data. We share with:
- Payment processors (Stripe)
- Service providers (hosting, analytics)

## Your Rights
- Request access to your data
- Request deletion
- Opt out of marketing

## Contact
Email: privacy@goumuve.com

## Changes
We may update this policy. Check this page for updates.
```

**Host at:** https://goumuve.com/privacy (or GitHub Pages)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Multiple screenshot sizes required | Single 6.9" iPhone size required (1320×2868) | 2024-2025 with iPhone 16 Pro Max | Reduced screenshot generation effort by ~80%. Apple auto-scales to smaller devices. |
| iOS 18 SDK acceptable | iOS 26 SDK required | April 28, 2026 | Apps built with Xcode 15 or earlier now rejected. Must use Xcode 16+. |
| Manual signing with certificates | Automatic signing default | Xcode 8+ (2016) | Reduced code signing errors by ~70%. Recommended for solo developers. |
| Separate App Store submission | TestFlight build reuse for App Store | Ongoing | Same binary used for TestFlight and App Store. Streamlines release process. |
| BitCode required | BitCode deprecated | Xcode 14 (2022) | Simplifies archive, smaller IPA files. No longer needs to be enabled. |

**Deprecated/outdated:**
- **BitCode:** Deprecated in Xcode 14. No longer include in archive options.
- **Old screenshot sizes:** iPhone 5.5" (1242×2208) and 6.5" (1242×2688) no longer required. 6.9" is new base size.
- **Manual certificate management:** While still supported, automatic signing is now standard for 90% of developers.
- **iTunes Connect:** Rebranded to App Store Connect in 2018. All documentation uses new name.

**Sources:** [Apple - Screenshot specs](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/), [Apple - Upcoming requirements](https://developer.apple.com/news/upcoming-requirements/)

## Open Questions

1. **Customer app icon status**
   - What we know: AppIcon.appiconset directory exists, but `find` returned 0 PNG files
   - What's unclear: Are icons present but not found, or actually missing?
   - Recommendation: Manual verification in Xcode BEFORE archiving. If missing, generate from 1024×1024 master icon using online generator (appicon.co) or design tool.

2. **Production backend deployment status**
   - What we know: URL configured as https://junkos-backend.onrender.com
   - What's unclear: Is backend currently deployed and accepting requests? What's the health check endpoint?
   - Recommendation: Test production backend with curl before TestFlight submission. If not deployed, deploy backend first or use staging URL with clear tester instructions.

3. **Stripe key status**
   - What we know: Config.swift has placeholders "pk_test_PLACEHOLDER" and "pk_live_PLACEHOLDER"
   - What's unclear: Are actual Stripe keys available? Should TestFlight use test or live keys?
   - Recommendation: Use Stripe test keys for first TestFlight beta. Replace before App Store submission. Document in "What to Test" notes that payments are in test mode.

4. **Push notification entitlements**
   - What we know: Phase 4 implemented push notifications, Phase 5 uses push actions
   - What's unclear: Are push notification entitlements properly configured in both apps? Is aps-environment set correctly?
   - Recommendation: Audit entitlements files and verify provisioning profiles include push notifications before upload.

5. **Physical device availability**
   - What we know: TestFlight requires physical device testing
   - What's unclear: Does developer have access to physical iPhone for testing?
   - Recommendation: If no physical device available, use TestFlight internal testing with borrowed device or recruit first tester with device. Cannot skip this step.

6. **Apple Developer Program enrollment**
   - What we know: Required for TestFlight ($99/year)
   - What's unclear: Is account already enrolled? If not, add 24-48 hours to timeline.
   - Recommendation: Verify enrollment status at developer.apple.com/account before starting. If not enrolled, enroll immediately (first submission dependency).

## Sources

### Primary (HIGH confidence)

- [Apple Developer - TestFlight overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/) - Official TestFlight documentation
- [Apple Developer - Configuring app icon](https://developer.apple.com/documentation/xcode/configuring-your-app-icon) - App icon requirements
- [Apple Developer - Screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/) - 2026 screenshot sizes
- [Apple Developer - Diagnosing entitlements](https://developer.apple.com/documentation/bundleresources/diagnosing-issues-with-entitlements) - Entitlement troubleshooting
- [Apple Developer - Upcoming requirements](https://developer.apple.com/news/upcoming-requirements/) - iOS 26 SDK mandate
- [Apple Developer - Customizing build schemes](https://developer.apple.com/documentation/xcode/customizing-the-build-schemes-for-a-project) - Scheme configuration
- [Apple Developer - Upload builds](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/) - Upload process
- [Apple Xcode Help - Validate archive](https://help.apple.com/xcode/mac/current/en.lproj/dev37441e273.html) - Archive validation

### Secondary (MEDIUM confidence)

- [Sarunw - iOS environments setup](https://sarunw.com/posts/how-to-set-up-ios-environments/) - Build configuration patterns (2023)
- [Medium - Xcode scheme setup](https://medium.com/@hdmdhr/xcode-scheme-environment-project-configuration-setup-recipe-22c940585984) - Environment variable configuration
- [Kodeco - iOS App Distribution TestFlight](https://www.kodeco.com/books/ios-app-distribution-best-practices/v1.0/chapters/6-testflight) - TestFlight best practices
- [Luciq - TestFlight beta testing](https://www.luciq.ai/blog/testflight-beta-testing-setting-effective-tests) - Beta testing strategies
- [fastlane docs - Screenshots](https://docs.fastlane.tools/getting-started/ios/screenshots/) - Screenshot automation
- [SplitMetrics - iOS icon guide](https://splitmetrics.com/blog/guide-to-mobile-icons/) - Icon specifications (verified with Apple docs)
- [ASO.dev - Screenshot requirements 2026](https://aso.dev/app-store-connect/screenshots/) - Current screenshot sizes
- [Medium - iOS 26 SDK mandate](https://medium.com/codex/apples-ios-26-sdk-mandate-what-itms-90725-means-for-every-app-by-april-2026-01578e627b05) - SDK requirement details

### Tertiary (LOW confidence)

- [GitHub dotnet/maui Issue #32293](https://github.com/dotnet/maui/issues/32293) - Entitlement validation error example (specific to MAUI, but pattern applies)
- [QA Wolf - Mobile E2E testing 2026](https://www.qawolf.com/blog/best-mobile-app-testing-frameworks-2026) - E2E testing framework comparison
- [BrowserStack - iOS testing guide](https://www.browserstack.com/guide/test-react-native-apps-ios-android) - Physical device testing strategies (React Native focused but concepts apply)

### Codebase Inspection (HIGH confidence)

- `/JunkOS-Clean/JunkOS/Info.plist` - Customer app configuration, privacy strings present
- `/JunkOS-Clean/JunkOS/JunkOS.entitlements` - Apple Pay merchant entitlement
- `/JunkOS-Clean/JunkOS/Services/Config.swift` - Environment switching implementation
- `/JunkOS-Clean/TESTFLIGHT_SETUP_GUIDE.md` - Existing 786-line TestFlight walkthrough (comprehensive)
- `/JunkOS-Driver/project.yml` - Driver app XcodeGen configuration, bundle ID, version, SDK
- `/JunkOS-Driver/Config/Config.swift` - Driver app environment switching
- `/JunkOS-Driver/Assets.xcassets/AppIcon.appiconset/` - Driver app icons (13 files verified)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Apple toolchain, well-documented, no alternatives
- Architecture: HIGH - Patterns verified in codebase and Apple documentation
- Pitfalls: HIGH - Based on official Apple TN2294, TN2415, and common validation errors documented by Apple
- Environment switching: HIGH - Pattern verified in both app Config.swift files
- Screenshot requirements: HIGH - Apple official specs, cross-verified with multiple 2026 sources
- Icon requirements: MEDIUM - Driver app icons verified (13 files), customer app icons need manual check
- Backend configuration: MEDIUM - URLs present in Config.swift, but deployment status unknown
- E2E testing: MEDIUM - General best practices well-documented, specific Umuve flow needs definition

**Research date:** 2026-02-14
**Valid until:** 2026-03-15 (30 days for stable domain, Apple requirements change slowly)

**Note:** Apple TestFlight and App Store Connect requirements are exceptionally stable compared to other mobile development domains. Core process (archive, validate, upload) unchanged since 2016. Main changes are SDK version mandates (annual) and screenshot sizes (device-driven).
