# App Store Deployment Checklist

Complete guide to deploying JunkOS Booking app to TestFlight and the App Store.

## Prerequisites

- [ ] **Apple Developer Account** ($99/year)
  - Enroll at https://developer.apple.com/programs/
  
- [ ] **App Store Connect Access**
  - Create app listing at https://appstoreconnect.apple.com/

- [ ] **EAS CLI Installed**
  ```bash
  npm install -g eas-cli
  eas login
  ```

## Phase 1: App Assets

### Required Assets
- [ ] **App Icon** (1024x1024px)
  - Save as `assets/icon.png`
  - No transparency, no rounded corners
  - PNG format

- [ ] **Splash Screen** (1284x2778px)
  - Save as `assets/splash.png`
  - PNG format

- [ ] **Screenshots** (Required sizes)
  - 6.7" Display: 1290x2796px (iPhone 14 Pro Max)
  - 6.5" Display: 1284x2778px (iPhone 11 Pro Max)
  - 5.5" Display: 1242x2208px (iPhone 8 Plus)
  - Take screenshots of all 6 screens

### Generate Icons
```bash
# Use figma-export or similar tool
# Or use online generator: appicon.co
```

## Phase 2: App Configuration

### Update app.json
```json
{
  "expo": {
    "name": "JunkOS Booking",
    "slug": "junkos-booking",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#ffffff"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.junkos.booking",
      "buildNumber": "1",
      "infoPlist": {
        "NSCameraUsageDescription": "JunkOS needs camera access to take photos of items for junk removal.",
        "NSPhotoLibraryUsageDescription": "JunkOS needs photo library access to select existing photos.",
        "NSLocationWhenInUseUsageDescription": "We use your location to improve service quality."
      }
    },
    "extra": {
      "eas": {
        "projectId": "YOUR_PROJECT_ID"
      }
    }
  }
}
```

### Configure EAS
```bash
eas build:configure
```

This creates `eas.json`:
```json
{
  "cli": {
    "version": ">= 5.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "ios": {
        "simulator": true
      }
    },
    "preview": {
      "distribution": "internal",
      "ios": {
        "simulator": false
      }
    },
    "production": {
      "distribution": "store",
      "ios": {
        "simulator": false
      }
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "your-apple-id@example.com",
        "ascAppId": "YOUR_ASC_APP_ID",
        "appleTeamId": "YOUR_TEAM_ID"
      }
    }
  }
}
```

## Phase 3: Build

### Create Production Build
```bash
# First build (creates certificates)
eas build --platform ios --profile production

# Subsequent builds
eas build --platform ios --profile production --auto-submit
```

**Build Time:** 15-30 minutes

### Manual Build (Alternative)
```bash
# Generate native iOS project
npx expo prebuild

# Open in Xcode
open ios/junkos-booking.xcworkspace

# Configure signing in Xcode:
# 1. Select project
# 2. Select target
# 3. Signing & Capabilities
# 4. Team: Select your Apple Developer account
# 5. Bundle Identifier: com.junkos.booking

# Archive and upload
# Product > Archive > Distribute App > App Store Connect
```

## Phase 4: TestFlight

### Upload to TestFlight
```bash
# Automatic submission (if configured in eas.json)
eas build --platform ios --profile production --auto-submit

# Manual submission
eas submit --platform ios
```

### Configure TestFlight
- [ ] Log in to App Store Connect
- [ ] Go to TestFlight tab
- [ ] Add internal testers (up to 100)
- [ ] Add external testers (requires review)
- [ ] Add "What to Test" notes

### Test Distribution
- [ ] Internal testing: Immediate (no review)
- [ ] External testing: 24-48 hours (Apple review)

### Tester Instructions
Send testers:
1. Install TestFlight from App Store
2. Use invitation link or redeem code
3. Open TestFlight and install JunkOS Booking
4. Provide feedback through TestFlight

## Phase 5: App Store Connect

### Create App Listing
- [ ] **App Information**
  - Name: JunkOS Booking
  - Subtitle: Fast & Reliable Junk Removal
  - Category: Lifestyle or Productivity
  - Content Rights: Own or licensed

- [ ] **Pricing**
  - Free (in-app payments handled by backend)

- [ ] **Privacy Policy**
  - Required URL: https://junkos.com/privacy
  - Data collection disclosure

- [ ] **App Description**
  ```
  JunkOS makes junk removal simple and stress-free. Book professional junk removal service in minutes.

  FEATURES:
  • Quick booking process
  • Upload photos of items
  • Flexible scheduling
  • Professional service
  • Upfront pricing

  HOW IT WORKS:
  1. Take photos of items to be removed
  2. Select service type and details
  3. Choose your preferred date and time
  4. Confirm and done!

  Our trained professionals handle everything from furniture to appliances, yard waste to electronics. We load, haul, and dispose of your items responsibly.
  ```

- [ ] **Keywords**
  - junk removal, haul, disposal, furniture removal, cleanup
  
- [ ] **Screenshots**
  - Upload all required sizes
  - First 3 are most important (shown in search)

- [ ] **Promotional Text** (editable without new version)
  ```
  🎉 Special offer: 20% off your first booking!
  ```

### App Review Information
- [ ] **Contact Information**
  - First Name, Last Name
  - Phone Number
  - Email Address

- [ ] **Demo Account** (for Apple reviewers)
  ```
  Username: reviewer@junkos.com
  Password: AppleReview2024!
  ```

- [ ] **Notes for Reviewer**
  ```
  Thank you for reviewing JunkOS Booking.

  TEST ACCOUNT:
  Email: reviewer@junkos.com
  Password: AppleReview2024!

  TESTING:
  1. Login with test account
  2. Complete booking flow
  3. Upload test photos (camera access required)
  4. Schedule test appointment

  NOTE: Payment processing happens on backend - no real charges in app.
  Backend API is hosted at: https://api.junkos.com
  ```

## Phase 6: App Review

### Prepare for Review
- [ ] **Working Backend**
  - Ensure production API is live
  - Test with demo account
  - Check all endpoints respond correctly

- [ ] **Privacy Compliance**
  - Privacy policy published
  - Data collection disclosed
  - Terms of service available

- [ ] **Legal Compliance**
  - No prohibited content
  - Age rating appropriate (4+)
  - Geographic restrictions if needed

### Submit for Review
```bash
# Via EAS
eas submit --platform ios --latest

# Or manually in App Store Connect
# 1. Go to "App Store" tab
# 2. Select version
# 3. Click "Add for Review"
# 4. Answer questions
# 5. Submit
```

**Review Time:** 24-48 hours (usually)

### Common Rejection Reasons
- ❌ Demo account doesn't work
- ❌ App crashes on launch
- ❌ Missing privacy policy
- ❌ Camera permission not justified
- ❌ Misleading screenshots

### If Rejected
1. Read rejection message carefully
2. Fix issues
3. Reply to reviewer or resubmit
4. Use "Resolution Center" for questions

## Phase 7: Post-Launch

### Monitoring
- [ ] Set up crash reporting (Sentry)
  ```bash
  npm install @sentry/react-native
  ```

- [ ] Monitor App Store reviews
- [ ] Track analytics
- [ ] Watch backend logs

### Updates
For new versions:
1. Update `version` and `buildNumber` in app.json
2. Build new version: `eas build --platform ios`
3. Submit to App Store Connect
4. Add "What's New" description
5. Submit for review

### Marketing
- [ ] App Store Optimization (ASO)
  - Optimize keywords
  - Update screenshots seasonally
  - Respond to reviews

- [ ] Social Media
  - Share app store link
  - Post screenshots/videos
  - Encourage reviews

## Emergency Procedures

### Critical Bug After Launch
1. **Hotfix**
   ```bash
   # Fix bug locally
   git commit -m "Hotfix: [description]"
   
   # Increment build number in app.json
   # "buildNumber": "2"
   
   # Build and submit
   eas build --platform ios --auto-submit
   ```

2. **Request Expedited Review**
   - In App Store Connect
   - Resolution Center > Request Expedited Review
   - Explain critical nature

### Remove from Sale
- App Store Connect > Pricing and Availability
- Set availability to "Remove from Sale"
- App remains installed for existing users

## Useful Commands

```bash
# Check build status
eas build:list

# View submission status
eas submit:list

# Update app store metadata
eas metadata:pull
eas metadata:push

# Generate new certificates
eas credentials

# View project info
eas project:info
```

## Resources

- **Expo Docs:** https://docs.expo.dev/
- **EAS Build:** https://docs.expo.dev/build/introduction/
- **App Store Connect:** https://appstoreconnect.apple.com/
- **Human Interface Guidelines:** https://developer.apple.com/design/human-interface-guidelines/

## Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Assets Creation | 2-4 hours | Day 1 |
| Configuration | 1 hour | Day 1 |
| First Build | 30 min | Day 1 |
| TestFlight Setup | 30 min | Day 1 |
| Internal Testing | 1-3 days | Day 2-4 |
| App Store Listing | 2 hours | Day 4 |
| External TestFlight | 1-2 days | Day 5-6 |
| App Review | 1-2 days | Day 7-8 |
| **TOTAL** | | **~7-8 days** |

## Checklist Summary

**Day 1-2: Preparation**
- [ ] Create app assets (icon, splash, screenshots)
- [ ] Configure app.json and eas.json
- [ ] Run production build
- [ ] Test locally

**Day 3-4: TestFlight**
- [ ] Upload to TestFlight
- [ ] Invite internal testers
- [ ] Gather feedback
- [ ] Fix any issues

**Day 5-6: App Store Prep**
- [ ] Create App Store listing
- [ ] Write descriptions
- [ ] Upload screenshots
- [ ] Create demo account
- [ ] Submit for external TestFlight (optional)

**Day 7-8: Review & Launch**
- [ ] Submit to App Store
- [ ] Monitor review status
- [ ] Respond to any questions
- [ ] Launch! 🚀

---

**Good luck with your launch! 🎉**
