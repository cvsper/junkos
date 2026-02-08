# TestFlight Setup Guide - Complete Walkthrough

**App:** JunkOS  
**Version:** 1.0.0 (Build 1)  
**Last Updated:** February 7, 2026

---

## Table of Contents

1. [Pre-Flight Checklist](#pre-flight-checklist)
2. [Apple Developer Account Setup](#apple-developer-account-setup)
3. [Code Signing Configuration](#code-signing-configuration)
4. [App Store Connect Setup](#app-store-connect-setup)
5. [Archive and Upload](#archive-and-upload)
6. [TestFlight Configuration](#testflight-configuration)
7. [Adding Beta Testers](#adding-beta-testers)
8. [Monitoring and Iteration](#monitoring-and-iteration)

---

## Pre-Flight Checklist

Before starting the TestFlight deployment process, verify your app is ready:

### ✅ App Configuration

```bash
# Check current configuration
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
xcodebuild -project JunkOS.xcodeproj -showBuildSettings | grep -E "PRODUCT_BUNDLE_IDENTIFIER|MARKETING_VERSION|CURRENT_PROJECT_VERSION"
```

**Current Configuration:**
- Bundle ID: `com.junkos.JunkOS`
- Marketing Version: `1.0`
- Build Number: `1`

### ✅ Info.plist Required Keys

Your Info.plist should contain:

- ✅ `CFBundleDisplayName` = "JunkOS"
- ✅ `CFBundleShortVersionString` = "1.0"
- ✅ `CFBundleVersion` = "1"
- ✅ `NSPhotoLibraryUsageDescription` (for photo picker)
- ✅ `NSCameraUsageDescription` (for camera access)
- ✅ `NSLocationWhenInUseUsageDescription` (for address)

### ✅ Assets Verification

```bash
# Check for app icon
ls -la JunkOS/Assets.xcassets/AppIcon.appiconset/

# Verify launch screen
ls -la JunkOS/LaunchScreen.storyboard || echo "Using UILaunchScreen (iOS 14+)"
```

Required assets:
- ✅ App Icon (all required sizes)
- ✅ Launch screen configured
- ✅ No missing image assets

### ✅ Build Verification

```bash
# Clean build folder
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
xcodebuild clean -project JunkOS.xcodeproj -scheme JunkOS

# Test build for Release configuration
xcodebuild -project JunkOS.xcodeproj -scheme JunkOS -configuration Release -sdk iphoneos CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO
```

Build should succeed with:
- ✅ 0 errors
- ✅ 0 warnings (ideally)
- ✅ No deprecated API usage

---

## Apple Developer Account Setup

### Step 1: Enroll in Apple Developer Program

**Cost:** $99 USD/year

**Enrollment Process:**

1. **Go to:** https://developer.apple.com/programs/enroll/
2. **Sign in** with your Apple ID
3. **Choose entity type:**
   - **Individual:** Personal account (fastest approval, 24-48 hours)
   - **Organization:** Business account (requires D-U-N-S number, longer approval)
4. **Complete enrollment:**
   - Provide personal/business information
   - Accept agreements
   - Pay $99 fee
5. **Wait for approval** (email confirmation)

**What you'll need:**
- Valid Apple ID
- Payment method (credit card)
- Government-issued photo ID (for individuals)
- D-U-N-S number (for organizations) - free from Dun & Bradstreet

### Step 2: Verify Account Status

Once enrolled:

1. Go to: https://developer.apple.com/account
2. Verify you see: "Membership" section with "Active" status
3. Check "Certificates, Identifiers & Profiles" is accessible

---

## Code Signing Configuration

### Option A: Automatic Signing (Recommended for Beginners)

Xcode manages certificates and profiles automatically.

**Steps:**

1. **Open Xcode project:**
   ```bash
   open ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj
   ```

2. **Select project** in Navigator (blue icon at top)

3. **Select JunkOS target** (not the project)

4. **Go to "Signing & Capabilities" tab**

5. **Check "Automatically manage signing"**

6. **Select your Team:**
   - Click "Team" dropdown
   - Select your Apple Developer account
   - If not listed, click "Add Account..." and sign in

7. **Verify Bundle Identifier:**
   - Should show: `com.junkos.JunkOS`
   - If you want to change it to `com.junkos.app`, update it here

8. **Check signing status:**
   - Should show green checkmark
   - If error, see [Troubleshooting](#troubleshooting)

**What Xcode creates automatically:**
- iOS Distribution Certificate (valid 1 year)
- App Store Provisioning Profile (valid until certificate expires)
- Registers App ID with capabilities

### Option B: Manual Signing (Advanced)

For more control over certificates and profiles.

**When to use manual:**
- Multiple developers/machines
- CI/CD pipelines
- Need specific certificate control
- Sharing profiles across team

**See:** [CODE_SIGNING_GUIDE.md](./CODE_SIGNING_GUIDE.md) for detailed manual signing instructions.

---

## App Store Connect Setup

### Step 1: Create App Record

1. **Go to:** https://appstoreconnect.apple.com
2. **Sign in** with your Apple Developer account
3. **Click "My Apps"**
4. **Click the "+" button** → "New App"

### Step 2: Fill App Information

**Platforms:** iOS

**Name:** JunkOS
- Must be unique in the App Store
- Max 30 characters
- Cannot include "Apple" or trademarked terms

**Primary Language:** English (U.S.)

**Bundle ID:** Select `com.junkos.JunkOS` (or your chosen bundle ID)
- Must match your Xcode project exactly
- Cannot be changed after submission

**SKU:** `junkos-ios-app`
- Internal identifier (not visible to users)
- Alphanumeric, no spaces
- Use lowercase for consistency

**User Access:** Full Access (default)

### Step 3: Set Up App Information

**Click your app** → **App Information**

#### Category
- **Primary Category:** Lifestyle
- **Secondary Category:** Business (optional)

#### Age Rating

Click "Edit" next to Age Rating:

1. **Unrestricted Web Access:** No
2. **Gambling:** No
3. **Contests:** No
4. **Simulated Gambling:** No
5. **Mature/Suggestive Themes:** None
6. **Horror/Fear Themes:** None
7. **Medical/Treatment Information:** No
8. **Profanity or Crude Humor:** None
9. **Sexual Content or Nudity:** None
10. **Violence:** None

**Result:** 4+ (Everyone)

#### App Subtitle

**Text:** "Junk Removal Made Easy"
- Max 30 characters
- Appears below app name in search results

### Step 4: Pricing and Availability

**Click "Pricing and Availability"** in left sidebar

**Price:** Free (App is free, service charges happen offline)

**Availability:**
- **All countries:** Yes (or select specific countries)
- **Pre-order:** No

### Step 5: Privacy Policy

**You need a privacy policy URL before submission.**

**Quick Options:**

1. **Create your own page:**
   - Host at `https://junkos.app/privacy`
   - Must be publicly accessible
   - See [Privacy Policy Template](#privacy-policy-template) below

2. **Use a generator:**
   - https://www.privacypolicygenerator.info/
   - https://app-privacy-policy-generator.firebaseapp.com/

3. **Use GitHub Pages (free):**
   ```bash
   # Create privacy.html and host on GitHub Pages
   echo "Your privacy policy" > privacy.html
   # Push to gh-pages branch
   ```

**Privacy Policy URL:** Add to App Store Connect:
- Go to App Information
- Scroll to "Privacy Policy URL"
- Enter: `https://junkos.app/privacy` (or your URL)
- Click "Save"

### Step 6: Support Information

**Support URL:** https://junkos.app/support (optional but recommended)

**Marketing URL:** https://junkos.app (optional)

**Copyright:** 2026 [Your Name or Company]

---

## Archive and Upload

### Step 1: Prepare for Archive

1. **Open Xcode project:**
   ```bash
   open ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj
   ```

2. **Select target device:**
   - Top toolbar, click device dropdown
   - Select **"Any iOS Device (arm64)"**
   - Do NOT select Simulator

3. **Clean build folder:**
   - Menu: **Product → Clean Build Folder**
   - Or press: **⌘⇧K**

### Step 2: Update Version/Build Number (if needed)

**When to increment:**
- **Marketing Version (1.0):** For public-facing version changes
- **Build Number (1):** For each upload to App Store Connect

**To increment build:**
1. Select project in Navigator
2. Select JunkOS target
3. Go to "General" tab
4. Update "Build" number (e.g., 1 → 2)

**Or use command line:**
```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
agvtool next-version -all  # Increments build number
```

### Step 3: Archive the App

1. **Menu: Product → Archive**
   - Or press: **⌘⇧B** (Build), then **Product → Archive**

2. **Wait for archive to complete** (1-5 minutes)
   - Progress shown in top toolbar
   - Watch for any warnings/errors

3. **Organizer opens automatically**
   - Shows list of archives
   - Your new archive should be at the top

### Step 4: Validate the Archive

**Before uploading, validate to catch issues early:**

1. **In Organizer, select your archive**

2. **Click "Validate App" button** (on right side)

3. **Select distribution method:**
   - Choose: **"App Store Connect"**
   - Click "Next"

4. **Distribution options:**
   - ✅ Upload your app's symbols to receive symbolicated reports from Apple
   - ✅ Include bitcode for iOS content (if available)
   - Click "Next"

5. **Automatically manage signing:** 
   - Leave checked (recommended)
   - Click "Next"

6. **Review info:**
   - Check app name, version, bundle ID
   - Click "Validate"

7. **Wait for validation** (1-2 minutes)
   - ✅ Success: "Validation successful"
   - ❌ Errors: See [Troubleshooting](#troubleshooting)

### Step 5: Upload to App Store Connect

1. **In Organizer, select your archive**

2. **Click "Distribute App" button**

3. **Select distribution method:**
   - Choose: **"App Store Connect"**
   - Click "Next"

4. **Distribution options:**
   - ✅ Upload
   - Click "Next"

5. **Automatically manage signing:**
   - Leave checked
   - Click "Next"

6. **Review info and click "Upload"**

7. **Wait for upload** (2-10 minutes depending on size)
   - Progress bar shows upload status
   - **Success:** "Upload Successful"

8. **Click "Done"**

### Step 6: Wait for Processing

**In App Store Connect:**

1. Go to: https://appstoreconnect.apple.com
2. Click "My Apps" → "JunkOS"
3. Click "TestFlight" tab
4. Under "iOS Builds" section, you'll see:
   - **Processing:** Yellow warning icon (10-30 minutes)
   - **Ready to Submit:** Green checkmark (processing complete)

**What happens during processing:**
- Binary is scanned for malware
- Compliance checks
- Symbol processing
- Build analysis

**You'll receive an email when:**
- ✅ Processing is complete
- ❌ Issues are found (Missing Compliance, etc.)

---

## TestFlight Configuration

### Step 1: Add Build to TestFlight

Once processing is complete:

1. **Go to App Store Connect** → **My Apps** → **JunkOS**
2. **Click "TestFlight" tab**
3. **You should see your build** under "iOS Builds"

### Step 2: Complete Compliance Information

**Export Compliance Required:**

1. **Click on your build** (e.g., "1.0 (1)")
2. **You'll see warning: "Missing Compliance"**
3. **Click "Manage"** or "Provide Export Compliance Information"

**Answer these questions:**

**Q1: Is your app designed to use cryptography or does it contain or incorporate cryptography?**
- **Answer: NO** (unless you're using encryption beyond standard HTTPS)
- JunkOS uses standard HTTPS which is exempt

**Result:** Compliance completed automatically

**If you answered YES:**
- You may need to submit an annual self-classification report
- See: https://developer.apple.com/documentation/security/complying_with_encryption_export_regulations

### Step 3: Set Up Test Information

**Add Test Information visible to beta testers:**

1. **In TestFlight tab, scroll down** to "Test Information"
2. **Click "Edit"** next to "What to Test"

**What to Test (Beta App Description):**
```
🎉 Welcome to JunkOS Beta!

This is our MVP (Minimum Viable Product) to validate the concept and gather feedback.

✨ WHAT'S WORKING:
• Complete booking flow (6 screens)
• Address input with validation
• Service selection (6 services)
• Optional photo upload
• Date & time picker
• Booking confirmation
• Smooth animations & haptics
• VoiceOver support

⚠️ WHAT'S NOT YET IMPLEMENTED:
• Backend integration (bookings are simulated)
• Payment processing
• Booking history
• User accounts

🧪 PLEASE TEST:
1. Complete a booking from start to finish
2. Try navigating back/forth between screens
3. Test form validation
4. Upload photos and remove them
5. Try on different devices
6. Test with VoiceOver enabled
7. Look for bugs, crashes, or confusing UX

💬 SEND FEEDBACK:
Use the TestFlight feedback feature (shake device → Send Feedback) or reply to the beta email.

Thank you for being an early tester! 🙏
```

3. **Feedback Email:** (Your email where tester feedback is sent)
   - Enter: `beta@junkos.app` or your email

4. **Click "Save"**

### Step 4: App Clip (if applicable)

**Skip this** - JunkOS doesn't use App Clips

---

## Adding Beta Testers

### Internal Testing (First Phase)

**Internal testers:**
- Up to 100 testers
- Anyone with an App Store Connect account on your team
- No review required
- Instant access to builds

**Steps:**

1. **In TestFlight tab, click "Internal Testing"** in left sidebar
2. **Click "+" to create a group** (or use default group)
3. **Name the group:** "Internal Team"
4. **Add testers:**
   - Click "+" next to Testers
   - Check boxes next to team members
   - Click "Add"
5. **Enable automatic distribution:**
   - Toggle ON "Automatically distribute to testers"
   - New builds auto-send to this group
6. **Save**

**Testers receive:**
- Email invitation
- Instructions to install TestFlight app
- Link to download your app

### External Testing (Second Phase)

**External testers:**
- Up to 10,000 testers
- Anyone with an email address
- Requires Beta App Review (first build only, ~24 hours)
- Email-based invitations

**Steps:**

1. **Click "External Testing"** in left sidebar
2. **Click "+" to create a group**
3. **Name the group:** "Beta Testers"
4. **Click "Add Build"**
   - Select your build version
   - Click "Next"
5. **Review Test Information** 
   - Check "What to Test" is filled in
   - Click "Submit for Review"

**Beta App Review checklist:**
- ✅ What to Test is filled in
- ✅ App doesn't crash on launch
- ✅ Privacy policy URL is valid
- ✅ Export compliance is complete
- ✅ No inappropriate content

6. **Wait for approval** (~24 hours)
   - Email notification when approved
   - Status shows "Ready to Test"

7. **Add external testers:**
   - Click "+" next to Testers
   - Click "Add New Testers"
   - Enter email addresses (comma or newline separated)
   - Click "Add"

**Tester invitation email includes:**
- Link to install TestFlight
- Redemption code
- Instructions to join beta

### Public Link Testing (Alternative)

**Create a public link** anyone can use:

1. **In External Testing group**
2. **Click "Enable Public Link"**
3. **Copy the link** (e.g., `https://testflight.apple.com/join/ABC123`)
4. **Share the link** (Twitter, email, website)

**Limits:**
- 10,000 total testers
- Link can be disabled anytime

---

## Monitoring and Iteration

### Dashboard Overview

**App Store Connect → TestFlight → Dashboard**

**Key metrics:**
- **Installs:** Total number of testers who installed
- **Sessions:** Number of times app was launched
- **Crashes:** Number of crashes reported
- **Feedback:** Tester comments

### Crash Reports

1. **Click "Crashes" tab** in TestFlight
2. **View crash details:**
   - Crash type
   - Device model
   - iOS version
   - Stack trace (if symbols uploaded)

**To debug crashes:**
```bash
# Download dSYM file from Xcode Organizer
# Match crash reports with symbols
# View in Xcode: Window → Organizer → Crashes
```

### Tester Feedback

**View feedback:**

1. **TestFlight → Feedback** tab
2. **Each feedback includes:**
   - Comment text
   - Screenshot (if attached)
   - Device info
   - iOS version
   - Build number

**Responding to feedback:**
- Reply via email (feedback email address)
- Add notes internally in App Store Connect
- Track issues in your bug tracker

### Releasing New Builds

**When to release a new build:**
- Critical bug fixes
- Major feedback addressed
- New features to test

**Process:**

1. **Increment build number** in Xcode
   ```bash
   agvtool next-version -all  # Now build 2
   ```

2. **Update release notes** (What to Test section)

3. **Archive and upload** (repeat steps above)

4. **Add to TestFlight group:**
   - Internal: Auto-distributed (if enabled)
   - External: Click "Add Build to Group"

5. **Submit for review** (external only, if significant changes)

### Graduation to Production

**When ready for App Store:**

1. **Click "App Store" tab** (not TestFlight)
2. **Prepare for submission:**
   - App description
   - Screenshots (5 per device size)
   - App preview video (optional)
   - Keywords
   - Support URL
   - Privacy policy URL
3. **Select build from TestFlight**
4. **Submit for review**
5. **Wait for App Store review** (24-48 hours)

---

## Privacy Policy Template

**Minimum viable privacy policy for JunkOS:**

```markdown
# Privacy Policy for JunkOS

**Last Updated:** February 7, 2026

## Introduction

JunkOS ("we", "our", "us") respects your privacy. This policy describes how we collect, use, and share information when you use our mobile application.

## Information We Collect

### Information You Provide
- **Address:** To schedule junk removal service
- **Photos:** Optional photos of items to be removed
- **Contact Information:** Email, phone number for booking confirmation

### Automatically Collected Information
- **Device Information:** Device model, iOS version
- **Usage Data:** App interactions, crash logs

## How We Use Your Information

- Provide junk removal services
- Process and confirm bookings
- Communicate about your service
- Improve our app and services

## Information Sharing

We do not sell your personal information. We may share information with:
- Service providers (payment processing, hosting)
- Legal requirements (if required by law)

## Data Retention

We retain your information for as long as necessary to provide services and comply with legal obligations.

## Your Rights

You may:
- Request access to your data
- Request deletion of your data
- Opt out of marketing communications

## Contact Us

Email: privacy@junkos.app
Address: [Your Business Address]

## Changes to This Policy

We may update this policy. Changes will be posted with a new "Last Updated" date.
```

**Host this on:**
- Your website (https://junkos.app/privacy)
- GitHub Pages (free)
- Notion (free, public page)

---

## Timeline Expectations

**Typical timeline from zero to TestFlight:**

| Phase | Duration | Notes |
|-------|----------|-------|
| Apple Developer enrollment | 24-48 hours | Individuals faster than orgs |
| Code signing setup | 10 minutes | With automatic signing |
| App Store Connect record | 5 minutes | Creating app entry |
| Archive and upload | 15-30 minutes | Depends on app size |
| Build processing | 10-30 minutes | Apple's servers |
| Export compliance | 2 minutes | One-time per app |
| Internal testing | Immediate | No review needed |
| Beta App Review | 12-24 hours | First external build only |
| External testing | Immediate | After review approval |

**Total time to first beta:** ~1-2 days (mostly waiting for approvals)

---

## Next Steps

After following this guide:

1. ✅ **Test with internal team first** (3-5 days)
2. ✅ **Fix any critical bugs found**
3. ✅ **Submit for external beta review**
4. ✅ **Add external testers** (25-50 people)
5. ✅ **Gather feedback** (1-2 weeks)
6. ✅ **Iterate based on feedback**
7. ✅ **Prepare for App Store submission**

---

## Additional Resources

**Apple Documentation:**
- [App Store Connect Help](https://help.apple.com/app-store-connect/)
- [TestFlight Documentation](https://developer.apple.com/testflight/)
- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)

**Tools:**
- [Fastlane](https://fastlane.tools/) - Automate screenshots, builds, releases
- [AppIcon Generator](https://www.appicon.co/) - Generate all icon sizes

**See also:**
- [TESTFLIGHT_QUICK_START.md](./TESTFLIGHT_QUICK_START.md) - TL;DR version
- [CODE_SIGNING_GUIDE.md](./CODE_SIGNING_GUIDE.md) - Deep dive on signing
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Common issues and solutions

---

**Questions?** Email: support@junkos.app

**Status:** ✅ Ready to deploy
