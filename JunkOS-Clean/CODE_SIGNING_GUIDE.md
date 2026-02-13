# Code Signing Guide - Complete Reference

**App:** Umuve  
**Last Updated:** February 7, 2026

---

## Table of Contents

1. [Code Signing Overview](#code-signing-overview)
2. [Automatic vs Manual Signing](#automatic-vs-manual-signing)
3. [Certificates Explained](#certificates-explained)
4. [App IDs and Bundle Identifiers](#app-ids-and-bundle-identifiers)
5. [Provisioning Profiles](#provisioning-profiles)
6. [Automatic Signing Setup](#automatic-signing-setup)
7. [Manual Signing Setup](#manual-signing-setup)
8. [Team Management](#team-management)
9. [CI/CD Signing](#cicd-signing)
10. [Troubleshooting Signing Issues](#troubleshooting-signing-issues)

---

## Code Signing Overview

### What is Code Signing?

Code signing is Apple's way of ensuring:
- **Identity:** App comes from you (verified developer)
- **Integrity:** App hasn't been modified since you signed it
- **Trust:** Users can trust the app source

### Components of Code Signing

```
┌─────────────────────────────────────┐
│         YOUR APP (Umuve)           │
└─────────────────────────────────────┘
                 │
                 ├─ Signed with ─┐
                 │                │
         ┌───────▼───────┐  ┌────▼──────────┐
         │  CERTIFICATE  │  │   PROFILE     │
         └───────────────┘  └───────────────┘
                 │                │
         ┌───────▼───────┐        │
         │  PRIVATE KEY  │        │
         └───────────────┘        │
                                  │
                          ┌───────▼────────┐
                          │    APP ID      │
                          └────────────────┘
```

**Certificate** = Your digital identity (who you are)  
**Private Key** = Secret key (proves it's really you)  
**App ID** = Unique identifier for your app  
**Provisioning Profile** = Permissions bundle (what your app can do)

---

## Automatic vs Manual Signing

### Automatic Signing (Recommended)

**✅ Pros:**
- Xcode handles everything
- Easy for beginners
- Automatically renews profiles
- Quick setup (2 minutes)
- Works for most apps

**❌ Cons:**
- Less control over certificates
- Can't share profiles easily
- Harder to debug signing issues
- Not ideal for teams

**Best for:**
- Solo developers
- Small projects
- Quick prototyping
- First-time App Store submissions

---

### Manual Signing (Advanced)

**✅ Pros:**
- Full control over certificates
- Easier to share with team
- Better for CI/CD
- Explicit configuration
- Easier to troubleshoot

**❌ Cons:**
- More complex setup
- Must manually create profiles
- Must manually renew certificates
- Requires understanding of process

**Best for:**
- Teams (multiple developers)
- CI/CD pipelines
- Multiple targets/schemes
- Enterprise distributions
- Advanced workflows

---

## Certificates Explained

### Certificate Types

| Type | Purpose | Validity | Platform |
|------|---------|----------|----------|
| **Development** | Run on devices during development | 1 year | iOS, macOS, tvOS |
| **Distribution** | Submit to App Store, TestFlight | 1 year | iOS, macOS, tvOS |
| **Apple Development** | Universal dev cert (Xcode 11+) | 1 year | All platforms |
| **Apple Distribution** | Universal dist cert (Xcode 11+) | 1 year | All platforms |

**For Umuve TestFlight, you need:**
- ✅ **Apple Distribution** certificate (or **iOS Distribution**)

### What's Inside a Certificate?

```
Certificate
├── Your Name / Company Name
├── Team ID (ABC123XYZ)
├── Serial Number
├── Expiration Date
├── Public Key
└── Apple's Signature
```

**Private Key** (stored separately):
- Lives in your Mac's Keychain
- **NEVER share or commit to git**
- Required to sign apps
- If lost, must create new certificate

---

## App IDs and Bundle Identifiers

### What is an App ID?

An **App ID** uniquely identifies your app to Apple's systems.

**Format:** `TEAM_ID.BUNDLE_ID`

**Example for Umuve:**
```
TEAM_ID: ABC123XYZ (Apple assigns this)
BUNDLE_ID: com.goumuve.app
APP_ID: ABC123XYZ.com.goumuve.app
```

### Bundle ID Naming Conventions

**Best practices:**

✅ **Good:**
- `com.yourcompany.appname` (reverse domain)
- `com.goumuve.app`
- `app.junkos.ios`

❌ **Bad:**
- `myapp` (too generic)
- `com.goumuve.com.ios.production` (too long)
- `Umuve` (not reverse domain)

**Rules:**
- Alphanumeric + dot + hyphen only
- Must start with letter
- Case-sensitive (but use lowercase)
- Max 255 characters
- Cannot use wildcards for App Store

### Creating an App ID

**Method 1: Automatic (via Xcode)**

When you enable automatic signing, Xcode creates the App ID automatically.

**Method 2: Manual (via Developer Portal)**

1. **Go to:** https://developer.apple.com/account
2. **Click:** Certificates, Identifiers & Profiles
3. **Click:** Identifiers → **+** button
4. **Select:** App IDs → Continue
5. **Select Type:** App → Continue
6. **Fill in:**
   - **Description:** "Umuve iOS App"
   - **Bundle ID:** Explicit → `com.goumuve.app`
   - **Capabilities:** (none needed for Umuve MVP)
7. **Click:** Continue → Register

---

## Provisioning Profiles

### What is a Provisioning Profile?

A provisioning profile is a **permissions bundle** that:
- Links your certificate to an App ID
- Specifies which devices can run the app (for dev profiles)
- Lists enabled capabilities
- Has an expiration date

**Types:**

| Type | Purpose | Devices | Duration |
|------|---------|---------|----------|
| **Development** | Run on test devices | Specific devices | 1 year |
| **Ad Hoc** | Beta testing outside TestFlight | Up to 100 devices | 1 year |
| **App Store** | TestFlight & App Store distribution | Any device | 1 year |
| **Enterprise** | In-house distribution | Any device | 1 year |

**For Umuve TestFlight:**
- ✅ **App Store** provisioning profile

### Profile Contents

```
Provisioning Profile (.mobileprovision)
├── App ID: com.goumuve.app
├── Certificates: [Apple Distribution Certificate]
├── Devices: [ALL] (for App Store profiles)
├── Entitlements: [None for Umuve MVP]
├── Team ID: ABC123XYZ
├── Expiration: 2027-02-07
└── Apple's Signature
```

---

## Automatic Signing Setup

### Prerequisites

- ✅ Active Apple Developer Program membership
- ✅ Xcode installed (latest version recommended)
- ✅ Internet connection (Xcode needs to communicate with Apple)

### Step-by-Step Setup

#### 1. Add Your Apple ID to Xcode

```bash
# Open Xcode
open ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj
```

**In Xcode:**
1. **Xcode menu** → **Preferences** (or **Settings** in newer Xcode)
2. **Accounts tab**
3. **Click "+"** (bottom left)
4. **Select "Apple ID"**
5. **Sign in** with your Apple Developer account credentials
6. **Verify:** You see your account with "Apple Developer Program" badge

#### 2. Download Certificates (if needed)

1. **In Accounts preferences**
2. **Select your Apple ID**
3. **Select your team** (on right side)
4. **Click "Download Manual Profiles"** button
   - This pulls down any existing certificates and profiles

#### 3. Enable Automatic Signing in Project

1. **Close Preferences**
2. **Select project** in Navigator (blue Umuve icon at top)
3. **Select "Umuve" target** (under TARGETS)
4. **Go to "Signing & Capabilities" tab**
5. **Check ✅ "Automatically manage signing"**
6. **Select Team:** Your Apple Developer account from dropdown
   - If multiple teams, select the one with "Agent" or "Admin" role
7. **Verify Bundle Identifier:** `com.goumuve.app`

**Expected result:**

```
✅ Signing Certificate: Apple Development
✅ Provisioning Profile: Xcode Managed Profile
```

**For Release/Archive:**

Switch to "Release" configuration (in scheme editor) and Xcode will automatically use:
```
✅ Signing Certificate: Apple Distribution
✅ Provisioning Profile: Xcode Managed Profile (App Store)
```

#### 4. Verify Signing Works

**Test development signing:**

1. Connect your iPhone/iPad
2. Select your device in toolbar
3. Press **⌘R** (Run)
4. App should install and launch on device

**Test archive signing:**

1. Select **"Any iOS Device (arm64)"** in toolbar
2. **Product → Archive**
3. Should complete without signing errors

---

## Manual Signing Setup

### When to Use Manual Signing

- Multiple team members need to share signing assets
- Setting up CI/CD pipeline
- Need explicit control over certificates
- Debugging signing issues
- Corporate/enterprise requirements

### Step 1: Create Distribution Certificate

#### Option A: Via Xcode (Easier)

1. **Xcode → Preferences → Accounts**
2. **Select your Apple ID → Select team**
3. **Click "Manage Certificates..."**
4. **Click "+" → "Apple Distribution"**
5. **Certificate created automatically**
6. **Click "Done"**

#### Option B: Via Developer Portal (More Control)

1. **Go to:** https://developer.apple.com/account
2. **Certificates, Identifiers & Profiles** → **Certificates**
3. **Click "+"** to create new certificate
4. **Select:** iOS Distribution (or Apple Distribution)
5. **Click "Continue"**

**Create Certificate Signing Request (CSR):**

6. **On your Mac:**
   - Open **Keychain Access** (Applications → Utilities)
   - Menu: **Keychain Access → Certificate Assistant → Request a Certificate from a Certificate Authority**
   - Fill in:
     - **User Email:** your@email.com
     - **Common Name:** Your Name
     - **CA Email:** (leave empty)
     - **Request:** Saved to disk
     - **Let me specify key pair information:** ✅
   - Click **Continue**
   - Save as: `UmuveDistribution.certSigningRequest`
   - **Key Size:** 2048 bits
   - **Algorithm:** RSA
   - Click **Continue**

7. **Back in browser:**
   - Click "Choose File"
   - Upload your `.certSigningRequest` file
   - Click "Continue"

8. **Download certificate:**
   - Click "Download"
   - File: `distribution.cer` (or `ios_distribution.cer`)

9. **Install certificate:**
   - Double-click downloaded `.cer` file
   - Opens in Keychain Access
   - Certificate installed in "login" keychain
   - **Verify:** Expand certificate to see private key underneath

**⚠️ IMPORTANT: Back Up Your Private Key**

```bash
# Export certificate + private key from Keychain
# Right-click certificate → Export
# Save as: Umuve_Distribution.p12
# Set a strong password
# Store securely (1Password, encrypted drive)
```

### Step 2: Create App ID (if not exists)

**Check if exists:**

1. **Go to:** https://developer.apple.com/account
2. **Identifiers** → **App IDs**
3. **Search for:** `com.goumuve.app`

**If not found, create it:**

1. **Click "+"**
2. **Select:** App IDs → Continue
3. **Type:** App → Continue
4. **Description:** Umuve iOS App
5. **Bundle ID:** Explicit → `com.goumuve.app`
6. **Capabilities:** 
   - Photo Library Usage (auto-detected from Info.plist)
   - Nothing else needed for MVP
7. **Continue → Register**

### Step 3: Create Provisioning Profile

1. **Go to:** https://developer.apple.com/account
2. **Profiles** → **Click "+"**
3. **Select:** App Store (under Distribution)
4. **Click "Continue"**
5. **Select App ID:** `com.goumuve.app`
6. **Click "Continue"**
7. **Select Certificate:** Choose your Apple Distribution certificate
8. **Click "Continue"**
9. **Profile Name:** `Umuve App Store`
10. **Click "Generate"**
11. **Download profile:** `Umuve_App_Store.mobileprovision`

### Step 4: Install Provisioning Profile

**Option A: Double-click** the `.mobileprovision` file

**Option B: Manual installation:**

```bash
# Copy to Xcode profiles directory
cp ~/Downloads/Umuve_App_Store.mobileprovision ~/Library/MobileDevice/Provisioning\ Profiles/
```

**Option C: Xcode will find it automatically** when you select manual signing

### Step 5: Configure Manual Signing in Xcode

1. **Open project in Xcode**
2. **Select project → Target "Umuve"**
3. **Go to "Signing & Capabilities" tab**
4. **UNcheck ❌ "Automatically manage signing"**

**For Debug configuration:**
5. **Click "Signing (Debug)" dropdown if collapsed**
6. **Provisioning Profile:** Select "Xcode Managed Profile" or a Dev profile
7. **Signing Certificate:** Apple Development

**For Release configuration:**
8. **Click "Signing (Release)" dropdown**
9. **Provisioning Profile:** Select "Umuve App Store" from dropdown
10. **Signing Certificate:** Apple Distribution

**Expected result:**
```
Debug:
✅ Signing Certificate: Apple Development
✅ Provisioning Profile: [Your Dev Profile]

Release:
✅ Signing Certificate: Apple Distribution
✅ Provisioning Profile: Umuve App Store
```

### Step 6: Verify Manual Signing

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean

# Build for Release (archive)
xcodebuild -project JunkOS.xcodeproj \
  -scheme Umuve \
  -configuration Release \
  -archivePath ~/Desktop/Umuve.xcarchive \
  archive

# Check signing
codesign -vv -d ~/Desktop/Umuve.xcarchive/Products/Applications/Umuve.app

# Should show:
# Authority=Apple Distribution: Your Name (TEAM_ID)
# Authority=Apple Worldwide Developer Relations Certification Authority
# Authority=Apple Root CA
```

---

## Team Management

### Roles and Permissions

| Role | Create Certs | Create Profiles | Upload Builds | Submit for Review |
|------|-------------|----------------|---------------|-------------------|
| **Account Holder** | ✅ | ✅ | ✅ | ✅ |
| **Admin** | ✅ | ✅ | ✅ | ✅ |
| **App Manager** | ❌ | ❌ | ✅ | ✅ |
| **Developer** | ❌ | ❌ | ✅ | ❌ |
| **Marketing** | ❌ | ❌ | ❌ | ❌ |

### Adding Team Members

1. **Go to:** https://appstoreconnect.apple.com
2. **Users and Access**
3. **Click "+"** (top right)
4. **Fill in:**
   - First Name, Last Name, Email
   - Role: Developer (for most team members)
   - Apps: Select "Umuve" or "All Apps"
5. **Click "Invite"**
6. They receive email invitation

### Sharing Signing Assets with Team

**⚠️ Security Note:** Only share with trusted team members.

**Method 1: Export from Keychain (Mac to Mac)**

1. **On your Mac:**
   ```bash
   # Open Keychain Access
   # Find: Apple Distribution: Your Name
   # Right-click → Export
   # Save as: Umuve_Signing.p12
   # Set strong password
   ```

2. **Share securely:**
   - Use 1Password, LastPass, or encrypted email
   - Include password separately

3. **Team member imports:**
   - Double-click `.p12` file
   - Enter password
   - Certificate + private key installed

4. **Download provisioning profile:**
   - Go to developer.apple.com/account
   - Download the same provisioning profile
   - Team member installs it

**Method 2: Fastlane Match (Recommended for Teams)**

See [CI/CD Signing](#cicd-signing) section below.

---

## CI/CD Signing

### Fastlane Match (Recommended)

**Fastlane Match** stores certificates and profiles in a git repo (encrypted).

#### Initial Setup

```bash
# Install fastlane
brew install fastlane

# Navigate to project
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean

# Initialize fastlane
fastlane init

# Set up match
fastlane match init
# Choose: git
# Enter a new private git repo URL (e.g., GitHub private repo)
```

#### Create and Store Signing Assets

```bash
# Generate and store App Store signing assets
fastlane match appstore --app_identifier com.goumuve.app

# Prompts for:
# - Git repo password (to encrypt certificates)
# - Apple Developer Portal credentials
```

**What Match does:**
1. Creates Distribution certificate (if needed)
2. Creates App Store provisioning profile
3. Encrypts both
4. Commits to private git repo
5. Installs on your Mac

#### Use in CI/CD

**GitHub Actions example:**

```yaml
# .github/workflows/testflight.yml
name: Deploy to TestFlight

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install dependencies
        run: |
          brew install fastlane
      
      - name: Sync code signing
        env:
          MATCH_PASSWORD: ${{ secrets.MATCH_PASSWORD }}
          FASTLANE_USER: ${{ secrets.APPLE_ID }}
          FASTLANE_PASSWORD: ${{ secrets.APPLE_PASSWORD }}
        run: |
          fastlane match appstore --readonly
      
      - name: Build and upload
        env:
          FASTLANE_USER: ${{ secrets.APPLE_ID }}
          FASTLANE_PASSWORD: ${{ secrets.APPLE_PASSWORD }}
        run: |
          fastlane beta
```

**Fastlane beta lane:**

```ruby
# fastlane/Fastfile
lane :beta do
  # Sync signing
  match(type: "appstore", readonly: true)
  
  # Increment build number
  increment_build_number
  
  # Build app
  build_app(
    scheme: "Umuve",
    export_method: "app-store"
  )
  
  # Upload to TestFlight
  upload_to_testflight(
    skip_waiting_for_build_processing: true
  )
end
```

---

## Troubleshooting Signing Issues

### Common Error: "No signing certificate found"

**Cause:** Certificate missing or not trusted.

**Solution:**

```bash
# Check certificates in keychain
security find-identity -v -p codesigning

# Should show:
# 1) ABC123... "Apple Development: Your Name (TEAM_ID)"
# 2) XYZ789... "Apple Distribution: Your Name (TEAM_ID)"

# If missing:
# Option 1: Download from Xcode Preferences → Accounts
# Option 2: Create new certificate (see above)
```

---

### Common Error: "No matching provisioning profile found"

**Cause:** Profile missing or doesn't match Bundle ID/capabilities.

**Solution:**

```bash
# List installed profiles
ls ~/Library/MobileDevice/Provisioning\ Profiles/

# Download profiles from Xcode
# Xcode → Preferences → Accounts → Download Manual Profiles

# Or manually download from developer.apple.com
```

---

### Common Error: "Provisioning profile doesn't include signing certificate"

**Cause:** Profile was created with a different certificate.

**Solution:**

1. Go to https://developer.apple.com/account
2. Profiles → Select your profile
3. Click "Edit"
4. Re-select your certificate
5. Click "Generate"
6. Download and install new profile

---

### Common Error: "Code signing is required for product type"

**Cause:** Signing is disabled or misconfigured.

**Solution:**

**In Xcode:**
1. Select target
2. Signing & Capabilities tab
3. Ensure "Automatically manage signing" is checked
4. OR manually select valid profile/certificate

---

### Common Error: "The app references non-public selectors"

**Cause:** Using private Apple APIs.

**Solution:**

Review code for:
- Private API usage
- Swizzling Apple methods
- Accessing undocumented frameworks

**For Umuve:** Should not apply (using only public APIs).

---

### Common Error: "Missing Info.plist keys"

**Cause:** Required privacy keys not in Info.plist.

**Solution:**

Check Info.plist contains:
```xml
<key>NSPhotoLibraryUsageDescription</key>
<string>We need access to your photo library so you can upload photos of items you want removed.</string>

<key>NSCameraUsageDescription</key>
<string>We need camera access so you can take photos of items you want removed.</string>
```

---

### Command-Line Debugging

**Check signing configuration:**

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean

# Show build settings
xcodebuild -project JunkOS.xcodeproj \
  -scheme Umuve \
  -showBuildSettings | grep -E "CODE_SIGN|PROVISIONING"

# Look for:
# CODE_SIGN_IDENTITY = Apple Distribution
# CODE_SIGN_STYLE = Automatic (or Manual)
# PROVISIONING_PROFILE_SPECIFIER = Profile Name
```

**Verify certificate chain:**

```bash
# List signing identities
security find-identity -v -p codesigning

# Check certificate validity
security find-certificate -c "Apple Distribution" -p | openssl x509 -text | grep -E "Subject:|Not After"
```

**Verify provisioning profile:**

```bash
# Decode profile (shows as XML)
security cms -D -i ~/Library/MobileDevice/Provisioning\ Profiles/*.mobileprovision

# Or use profile inspector
# https://github.com/chockenberry/Provisioning
```

---

## Quick Reference

### Certificate Locations

```
Keychain:
~/Library/Keychains/login.keychain-db

Certificates:
/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk/Certificates/

Provisioning Profiles:
~/Library/MobileDevice/Provisioning Profiles/
```

### Important Commands

```bash
# List certificates
security find-identity -v -p codesigning

# Verify code signature
codesign -vv -d /path/to/app

# Show provisioning profiles
ls ~/Library/MobileDevice/Provisioning\ Profiles/

# Remove all profiles (clean slate)
rm ~/Library/MobileDevice/Provisioning\ Profiles/*.mobileprovision

# Show Xcode paths
xcode-select -p
```

---

## Best Practices

### ✅ Do's

- ✅ Use automatic signing for solo projects
- ✅ Use manual signing for teams and CI/CD
- ✅ Back up certificates + private keys (export as .p12)
- ✅ Store .p12 files in 1Password/LastPass
- ✅ Use Fastlane Match for team signing
- ✅ Renew certificates before expiration
- ✅ Document your signing setup

### ❌ Don'ts

- ❌ Commit certificates/keys to git
- ❌ Share private keys insecurely (email, Slack)
- ❌ Use development certificates for distribution
- ❌ Create duplicate certificates (max 3 per type)
- ❌ Hardcode provisioning profile UUIDs
- ❌ Forget to back up signing assets

---

## Additional Resources

**Apple Documentation:**
- [Code Signing Guide](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/)
- [Certificates Help](https://help.apple.com/xcode/mac/current/#/dev60b6fbbc7)
- [Managing Signing Assets](https://developer.apple.com/support/code-signing/)

**Tools:**
- [Fastlane Match](https://docs.fastlane.tools/actions/match/)
- [Provisioning Plugin (Xcode)](https://github.com/chockenberry/Provisioning)

**See also:**
- [TESTFLIGHT_SETUP_GUIDE.md](./TESTFLIGHT_SETUP_GUIDE.md)
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

**Last Updated:** February 7, 2026  
**Questions?** support@goumuve.com
