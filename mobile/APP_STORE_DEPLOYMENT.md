# iOS App Store Deployment Guide for JunkOS

Source: https://medium.com/@tusharkumar27864/best-practices-for-deploying-your-react-native-app-to-the-ios-app-store-92b6a0ddcba6

## Prerequisites

- ✅ Apple Developer account ($99/year)
- ✅ Mac with Xcode installed (latest version)
- ✅ React Native app running well in development
- ✅ Real iOS devices for testing (not just simulator)

---

## Step 1: Production Readiness

### Remove Development Code
```javascript
// ❌ BAD: Console logs in production
console.log("User clicked button!");

// ✅ GOOD: Conditional logging
if (__DEV__) {
  console.log("This only shows in development");
}
```

### Test on Real Devices
- Simulator is not enough — borrow iPhones to test on different models
- Test all features (camera, maps, payments, push notifications)
- Check performance on older iOS versions

---

## Step 2: App Store Connect Setup

1. Go to [App Store Connect](https://appstoreconnect.apple.com/)
2. Create "New App" in "My Apps" section
3. Fill in:
   - App name: **JunkOS**
   - Bundle ID: `com.junkos.booking` (MUST be unique)
   - Description, pricing, category
   - Screenshots (1290x2796 for iPhone 14 Pro Max)

### Bundle ID Configuration
```xml
<!-- In Info.plist -->
<key>CFBundleIdentifier</key>
<string>com.junkos.booking</string>
```

**Critical:** Bundle ID must be unique across ALL App Store apps.

---

## Step 3: Certificates & Provisioning Profiles

### What You Need
- **Distribution Certificate** — Your digital signature
- **Provisioning Profile** — Connects app to certificate

### Recommended: Use Fastlane
```bash
# Automate certificate management
fastlane match development
fastlane match appstore
```

**Manual approach:** Xcode → Preferences → Accounts → Manage Certificates

---

## Step 4: Production Configuration

### App Icon
- Generate all required sizes (20x20 to 1024x1024)
- Use [appicon.co](https://appicon.co/) or similar tool
- Add to `ios/JunkOS/Images.xcassets/AppIcon.appiconset/`

### Permission Descriptions (Info.plist)
```xml
<!-- Camera for photo upload -->
<key>NSCameraUsageDescription</key>
<string>We need camera access to photograph items for accurate estimates</string>

<!-- Photo library -->
<key>NSPhotoLibraryUsageDescription</key>
<string>Select photos of items you want removed</string>

<!-- Location for address input -->
<key>NSLocationWhenInUseUsageDescription</key>
<string>We use your location to prefill your service address</string>
```

### Environment Variables
```javascript
// ❌ BAD: Hardcoded API keys
const API_URL = "https://api.junkos.com";

// ✅ GOOD: Environment-based
const API_URL = __DEV__
  ? "http://localhost:5000"
  : "https://api.junkos.com";

// ✅ BETTER: Use react-native-config
import Config from 'react-native-config';
const API_URL = Config.API_URL;
```

---

## Step 5: Build & Archive

### In Xcode:
1. Open `ios/JunkOS.xcworkspace` (NOT .xcodeproj)
2. Select "Any iOS Device" (not simulator)
3. Product → Archive
4. Wait 5-10 minutes (get coffee ☕)

### Common Build Errors:
```bash
# If archive fails, try:
cd ios
pod install
cd ..
npx react-native clean-ios-build
```

---

## Step 6: TestFlight Testing (CRITICAL)

**Don't skip this!** TestFlight catches issues you'll miss:
- Push notifications not working
- Deep links broken
- Crashes on specific iOS versions
- Payment processing issues

### Steps:
1. Upload archive to App Store Connect
2. Add internal testers (team members)
3. Test all features on real devices
4. Fix bugs before public release

**Minimum testing:** 3 days with 5+ testers on different devices

---

## Step 7: App Store Submission

### Metadata Required:
- **App Name:** JunkOS
- **Subtitle:** Modern junk removal booking
- **Description:** 500-4000 characters (compelling copy!)
- **Keywords:** junk removal, hauling, booking, waste, declutter (max 100 chars)
- **Screenshots:** 6.7" (iPhone 14 Pro Max) + 5.5" (iPhone 8 Plus)
- **Preview Video:** Optional but recommended (30 seconds)
- **Age Rating:** 4+ (no objectionable content)
- **Privacy Policy URL:** Required (host on GitHub Pages)

### Review Checklist:
- ✅ App works without crashing
- ✅ All features work as described
- ✅ No placeholder content
- ✅ Privacy policy URL working
- ✅ Support URL working
- ✅ Screenshots accurate
- ✅ In-app purchases configured (if using Stripe)

**Submit → Wait 24-48 hours for review**

---

## Common Problems & Solutions

### Problem 1: App Size Too Large
```javascript
// ❌ BEFORE: Importing entire libraries
import moment from 'moment'; // 67 KB

// ✅ AFTER: Import only what you need
import { format } from 'date-fns/format'; // 5 KB
```

**Enable Hermes engine** (reduces app size by ~30%):
```javascript
// ios/Podfile
use_react_native!(
  :path => config[:reactNativePath],
  :hermes_enabled => true // Add this
)
```

### Problem 2: App Rejected for Crash
```javascript
// ❌ BEFORE: Missing error handling
const stripeModule = NativeModules.StripePayments;
stripeModule.initialize();

// ✅ AFTER: Proper error handling
try {
  const stripeModule = NativeModules.StripePayments;
  if (stripeModule) {
    stripeModule.initialize();
  }
} catch (error) {
  console.error('Stripe not available:', error);
  // Show fallback payment UI
}
```

### Problem 3: Missing Privacy Policy
**Required by Apple!** Even simple apps need one.

**Quick solution:**
1. Generate at [PrivacyPolicies.com](https://www.privacypolicies.com/)
2. Host on GitHub Pages or your website
3. Add URL to App Store Connect

---

## Automation with Fastlane

### Install:
```bash
cd ios
gem install fastlane
fastlane init
```

### Fastlane Configuration (`ios/Fastfile`):
```ruby
lane :beta do
  increment_build_number(xcodeproj: "JunkOS.xcodeproj")
  build_app(
    workspace: "JunkOS.xcworkspace",
    scheme: "JunkOS"
  )
  upload_to_testflight
  slack(message: "New TestFlight build uploaded!")
end

lane :release do
  increment_build_number(xcodeproj: "JunkOS.xcodeproj")
  build_app(
    workspace: "JunkOS.xcworkspace",
    scheme: "JunkOS"
  )
  upload_to_app_store
end
```

### Package.json scripts:
```json
{
  "scripts": {
    "deploy:testflight": "cd ios && fastlane beta",
    "deploy:appstore": "cd ios && fastlane release"
  }
}
```

**Deploy to TestFlight:**
```bash
npm run deploy:testflight
```

---

## Key Lessons

### Version vs Build Number
- **Version:** User-facing (1.0.0, 1.1.0, 2.0.0) — semantic versioning
- **Build Number:** Internal (1, 2, 3, 4) — increments with each upload

### Important Notes
- ✅ **Bitcode is deprecated** — don't enable it
- ✅ **Build for "Any iOS Device"** — simulator builds won't work
- ✅ **Export and backup certificates** — you'll regret it if you lose them
- ✅ **Test payment flows thoroughly** — Stripe test mode vs live mode
- ✅ **Add error tracking** (Sentry) — catch production crashes

---

## JunkOS-Specific Checklist

### Before Submission:
- [ ] Apple Developer account active
- [ ] Bundle ID registered: `com.junkos.booking`
- [ ] App icons generated (all sizes)
- [ ] Privacy policy published
- [ ] Backend API running on production URL
- [ ] Stripe keys configured (live, not test)
- [ ] Push notifications configured (APNs)
- [ ] TestFlight tested by 5+ users for 3+ days
- [ ] Screenshots captured (booking flow, success)
- [ ] App description written (compelling copy)
- [ ] Support email set up (support@junkos.com)

### Post-Submission:
- [ ] Monitor App Store Connect for review status
- [ ] Respond to Apple feedback within 24 hours
- [ ] Set up analytics (Firebase, Mixpanel)
- [ ] Prepare marketing materials for launch
- [ ] Plan update schedule (monthly releases)

---

## Timeline Estimate

- **Initial setup:** 1-2 days (certificates, App Store Connect)
- **Build & TestFlight:** 3-5 days (testing + fixes)
- **App Store review:** 1-3 days (Apple's timeline)
- **Total:** ~1 week from code complete to App Store

---

## Resources

- **App Store Connect:** https://appstoreconnect.apple.com/
- **Fastlane:** https://fastlane.tools/
- **Apple Human Interface Guidelines:** https://developer.apple.com/design/human-interface-guidelines/
- **Privacy Policy Generator:** https://www.privacypolicies.com/
- **App Icon Generator:** https://appicon.co/

---

**Updated:** 2026-02-06  
**Status:** Ready for implementation once React Native app is built
