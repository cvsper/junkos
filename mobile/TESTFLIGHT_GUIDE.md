# TestFlight Deployment Guide

Complete guide for deploying Umuve iOS app to TestFlight for beta testing.

## 📋 Prerequisites

Before you begin, ensure you have:

- [x] **Apple Developer Account** ($99/year)
- [x] **App Store Connect** access
- [x] **Expo account** (free at expo.dev)
- [x] **EAS CLI** installed (`npm install -g eas-cli`)
- [x] Completed app with all screens functional
- [x] App icons and splash screens ready
- [x] Privacy policy URL (required for App Store)

## 🎯 Step 1: Apple Developer Setup

### 1.1 Create App Identifier

1. Go to [Apple Developer Portal](https://developer.apple.com/account)
2. Navigate to **Certificates, Identifiers & Profiles**
3. Click **Identifiers** → **+** (Add new)
4. Select **App IDs** → **App**
5. Enter:
   - **Description**: Umuve Mobile
   - **Bundle ID**: `com.goumuve.mobile` (must match `app.json`)
6. **Capabilities** - Enable:
   - Push Notifications
   - Apple Pay (if using)
7. Click **Continue** → **Register**

### 1.2 Create Provisioning Profile

1. In Developer Portal, go to **Profiles**
2. Click **+** (Add new)
3. Select **iOS App Development** → **Continue**
4. Choose **App ID**: `com.goumuve.mobile`
5. Select **Certificates** (your development certificate)
6. Select **Devices** (register test devices)
7. Name: `Umuve Development`
8. Click **Generate** → **Download**

## 🔨 Step 2: EAS Build Configuration

### 2.1 Login to Expo

```bash
eas login
```

Enter your Expo account credentials.

### 2.2 Configure EAS

```bash
cd ~/Documents/programs/webapps/junkos/mobile
eas build:configure
```

This creates `eas.json`:

```json
{
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
      "distribution": "store"
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "your-apple-id@example.com",
        "ascAppId": "1234567890",
        "appleTeamId": "ABCDEFGHIJ"
      }
    }
  }
}
```

### 2.3 Update app.json

Ensure your `app.json` has:

```json
{
  "expo": {
    "name": "Umuve",
    "slug": "umuve-mobile",
    "version": "1.0.0",
    "ios": {
      "bundleIdentifier": "com.goumuve.mobile",
      "buildNumber": "1",
      "supportsTablet": false
    },
    "extra": {
      "eas": {
        "projectId": "your-project-id-from-expo"
      }
    }
  }
}
```

### 2.4 Get Expo Project ID

```bash
eas project:info
```

Copy the Project ID and add it to `app.json` → `extra.eas.projectId`.

## 🏗️ Step 3: Build for TestFlight

### 3.1 Create Production Build

```bash
eas build --platform ios --profile production
```

This will:
1. Upload your code to Expo servers
2. Build the iOS app in the cloud
3. Sign it with your Apple certificates
4. Generate an `.ipa` file
5. Take ~20-30 minutes

**Follow prompts:**
- "Generate new credentials?" → **Yes** (first time)
- "Sign in to Apple account?" → **Yes**
- Enter Apple ID and app-specific password

### 3.2 Monitor Build

View build status:
```bash
eas build:list
```

Or check [expo.dev/builds](https://expo.dev/accounts/[your-account]/projects/umuve-mobile/builds).

### 3.3 Download Build (Optional)

Once complete:
```bash
eas build:download --build-id <build-id>
```

## 📱 Step 4: App Store Connect Setup

### 4.1 Create App in App Store Connect

1. Go to [App Store Connect](https://appstoreconnect.apple.com)
2. Click **My Apps** → **+** → **New App**
3. Enter:
   - **Platform**: iOS
   - **Name**: Umuve
   - **Primary Language**: English (U.S.)
   - **Bundle ID**: `com.goumuve.mobile`
   - **SKU**: `umuve-mobile-001` (unique identifier)
   - **User Access**: Full Access
4. Click **Create**

### 4.2 Fill App Information

Navigate to your app → **App Information**:

- **Category**: Productivity or Business
- **Content Rights**: Check if applicable
- **Age Rating**: Complete questionnaire
- **Privacy Policy URL**: `https://goumuve.com/privacy`
- **Support URL**: `https://goumuve.com/support`

## 🚀 Step 5: Submit to TestFlight

### 5.1 Automatic Submission (Recommended)

```bash
eas submit --platform ios --profile production
```

This uploads the `.ipa` directly to App Store Connect.

### 5.2 Manual Upload (Alternative)

If automatic submission fails:

1. Download `.ipa` from Expo
2. Open **Transporter** app (Mac App Store)
3. Drag `.ipa` into Transporter
4. Click **Deliver**

## 🧪 Step 6: TestFlight Configuration

### 6.1 Add Test Information

In App Store Connect → **TestFlight** → **Test Information**:

1. **Beta App Description**:
   ```
   Umuve makes junk removal simple. Book a pickup in minutes:
   • Take photos of your items
   • Choose your pickup time
   • Pay securely
   • We haul it away!
   ```

2. **Beta App Review Information**:
   - **First Name**: Your first name
   - **Last Name**: Your last name
   - **Email**: your-email@goumuve.com
   - **Phone**: Your phone number

3. **Test Credentials** (for reviewer):
   - **Username**: test@goumuve.com
   - **Password**: TestPassword123!
   - **Notes**: "Use test Stripe card 4242 4242 4242 4242"

### 6.2 Export Compliance

For most apps:
- **Uses Encryption**: Yes
- **Exempt from regulations**: Yes (if only HTTPS)
- **Submit annual reports**: No

### 6.3 Add Internal Testers

1. Go to **TestFlight** → **Internal Testing**
2. Click **+** next to Testers
3. Add team members (up to 100)
4. They'll receive email invitations

### 6.4 Add External Testers (Optional)

1. Go to **TestFlight** → **External Testing**
2. Create a new group (e.g., "Beta Testers")
3. Add testers by email (up to 10,000)
4. **Submit for Beta App Review** (1-2 days)

## 📲 Step 7: Testing

### 7.1 Install TestFlight

Testers need:
1. **TestFlight** app from App Store
2. Invitation email from App Store Connect
3. iOS 13.0 or later

### 7.2 Test the App

Verify all features:
- [ ] Login/Register
- [ ] Camera permissions
- [ ] Location services
- [ ] Photo upload
- [ ] Address input
- [ ] Date/time picker
- [ ] Stripe payment (test mode)
- [ ] Booking confirmation
- [ ] Push notifications (if enabled)

### 7.3 Collect Feedback

TestFlight provides:
- **Crash logs**
- **Feedback** from testers
- **Usage analytics**

Access in App Store Connect → **TestFlight** → **Builds**.

## 🔄 Step 8: Updating the App

### 8.1 Increment Build Number

In `app.json`:
```json
{
  "ios": {
    "buildNumber": "2"  // Increment for each build
  }
}
```

Or increment version:
```json
{
  "version": "1.0.1"
}
```

### 8.2 Rebuild and Submit

```bash
eas build --platform ios --profile production
eas submit --platform ios --profile production
```

## 🐛 Troubleshooting

### Build Fails

**"Invalid Bundle ID"**
- Ensure `app.json` bundle ID matches Apple Developer Portal

**"No valid certificates"**
- Run `eas credentials` to regenerate

**"Build timeout"**
- Check Expo status page
- Retry: `eas build --platform ios --profile production --clear-cache`

### Submission Fails

**"Missing compliance"**
- Add export compliance info in App Store Connect

**"Invalid binary"**
- Ensure `buildNumber` increments for each upload

**"Missing required icon"**
- Check `assets/icon.png` is 1024x1024 PNG

### TestFlight Issues

**"App not appearing in TestFlight"**
- Wait 10-15 minutes for processing
- Check **Activity** tab for status

**"Crash on launch"**
- Check crash logs in App Store Connect
- Verify API_BASE_URL is accessible
- Test offline mode

## 📊 Analytics & Monitoring

### View TestFlight Metrics

App Store Connect → **TestFlight** → **Builds**:
- **Installs**: Number of testers who installed
- **Sessions**: App opens
- **Crashes**: Crash rate and logs

### Expo Dashboard

[expo.dev/accounts/[your-account]/projects/umuve-mobile](https://expo.dev):
- Build history
- Submit logs
- Project settings

## 🎓 Best Practices

1. **Test Thoroughly** before each TestFlight build
2. **Increment Build Number** for every upload
3. **Provide Clear Test Instructions** in Beta App Description
4. **Use Test Stripe Keys** in TestFlight builds
5. **Collect Feedback** from testers regularly
6. **Fix Critical Bugs** quickly with new builds
7. **Monitor Crash Reports** daily
8. **Limit External Testers** initially (start with 10-20)

## 🔐 Security Checklist

- [ ] Environment variables use test/staging values
- [ ] API endpoints point to staging server (not production)
- [ ] Stripe keys are test keys
- [ ] Debug logging disabled
- [ ] Test accounts created for reviewers
- [ ] Privacy policy and terms linked

## 📅 Timeline

| Step | Duration |
|------|----------|
| Apple Developer setup | 1-2 hours |
| EAS configuration | 30 minutes |
| Build creation | 20-30 minutes |
| App Store Connect setup | 1 hour |
| TestFlight processing | 10-15 minutes |
| Beta App Review (external) | 1-2 days |

**Total for internal testing**: ~4 hours  
**Total for external testing**: ~2-3 days

## 🆘 Support Resources

- **EAS Build Docs**: https://docs.expo.dev/build/introduction/
- **TestFlight Docs**: https://developer.apple.com/testflight/
- **Expo Forum**: https://forums.expo.dev/
- **Apple Developer Support**: https://developer.apple.com/contact/

---

**Next Steps**: Once TestFlight testing is complete, see [APP_STORE_CHECKLIST.md](./APP_STORE_CHECKLIST.md) for production App Store submission.
