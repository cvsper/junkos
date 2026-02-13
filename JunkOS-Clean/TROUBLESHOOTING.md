# TestFlight Troubleshooting Guide

**App:** Umuve  
**Last Updated:** February 7, 2026

---

## Table of Contents

1. [Code Signing Errors](#code-signing-errors)
2. [Upload Failures](#upload-failures)
3. [App Store Connect Issues](#app-store-connect-issues)
4. [TestFlight Processing Issues](#testflight-processing-issues)
5. [Tester Installation Problems](#tester-installation-problems)
6. [Build Issues](#build-issues)
7. [Validation Errors](#validation-errors)
8. [Beta Review Rejections](#beta-review-rejections)
9. [Crash Reports](#crash-reports)
10. [General Debugging](#general-debugging)

---

## Code Signing Errors

### Error: "No signing certificate found"

**Symptoms:**
```
Error: No signing certificate "Apple Distribution" found
```

**Causes:**
- Certificate not installed
- Certificate expired
- Keychain locked or corrupted

**Solutions:**

#### Solution 1: Check Certificate Exists

```bash
# List all signing certificates
security find-identity -v -p codesigning

# Should show:
# 1) ABC... "Apple Development: Your Name (TEAM_ID)"
# 2) XYZ... "Apple Distribution: Your Name (TEAM_ID)"
```

If missing, see Solution 2.

#### Solution 2: Download Certificate from Xcode

1. **Xcode → Preferences (Settings) → Accounts**
2. **Select your Apple ID**
3. **Select your Team**
4. **Click "Download Manual Profiles"**
5. **Close and try again**

#### Solution 3: Create New Certificate

1. **Go to:** https://developer.apple.com/account
2. **Certificates, Identifiers & Profiles → Certificates**
3. **Click "+"**
4. **Select:** Apple Distribution
5. **Follow:** [Certificate creation steps](./CODE_SIGNING_GUIDE.md#creating-distribution-certificate)

#### Solution 4: Unlock Keychain

```bash
# If keychain is locked
security unlock-keychain ~/Library/Keychains/login.keychain-db

# Enter your Mac password
```

---

### Error: "No matching provisioning profiles found"

**Symptoms:**
```
Error: No profiles for 'com.goumuve.app' were found
```

**Causes:**
- Profile not downloaded
- Bundle ID mismatch
- Profile expired
- Profile doesn't include your certificate

**Solutions:**

#### Solution 1: Download Profiles

**In Xcode:**
1. **Preferences → Accounts**
2. **Select Team**
3. **Click "Download Manual Profiles"**

#### Solution 2: Check Bundle ID Match

**In Xcode:**
1. **Select project → Target**
2. **General tab**
3. **Bundle Identifier:** Must be `com.goumuve.app` (exact match)

**In Developer Portal:**
1. **Go to:** https://developer.apple.com/account
2. **Identifiers → App IDs**
3. **Find:** `com.goumuve.app`
4. **Verify it exists and matches**

#### Solution 3: Recreate Provisioning Profile

1. **Go to:** https://developer.apple.com/account
2. **Profiles → Click your profile name**
3. **Click "Edit"**
4. **Reselect your certificate**
5. **Generate → Download**
6. **Double-click to install**

#### Solution 4: Let Xcode Manage It

1. **Select target in Xcode**
2. **Signing & Capabilities**
3. **Check ✅ "Automatically manage signing"**
4. **Select Team**
5. **Xcode creates profile automatically**

---

### Error: "Provisioning profile doesn't include signing certificate"

**Symptoms:**
```
The provisioning profile doesn't include the currently selected signing certificate
```

**Cause:**
Profile was created with a different certificate than what Xcode is trying to use.

**Solutions:**

#### Solution 1: Regenerate Profile with Correct Certificate

1. **Go to:** https://developer.apple.com/account
2. **Profiles → Select profile → Edit**
3. **Uncheck all certificates → Check your current certificate**
4. **Generate → Download → Install**

#### Solution 2: Use Automatic Signing

1. **Xcode → Target → Signing & Capabilities**
2. **Enable "Automatically manage signing"**
3. **Xcode handles certificate-profile matching**

---

### Error: "Revoked signing certificate"

**Symptoms:**
```
Your signing certificate has been revoked
```

**Cause:**
Someone revoked the certificate in the Developer Portal.

**Solution:**

1. **Create new certificate:**
   - Follow [Certificate creation guide](./CODE_SIGNING_GUIDE.md)

2. **Update all provisioning profiles:**
   - Go to Developer Portal
   - Edit each profile
   - Select new certificate
   - Regenerate and download

3. **Install in Xcode:**
   - Double-click new certificate
   - Download profiles via Xcode Preferences

---

## Upload Failures

### Error: "Upload failed: Network error"

**Symptoms:**
- Upload progress bar stalls
- "Preparing..." stuck forever
- Network timeout errors

**Solutions:**

#### Solution 1: Check Internet Connection

```bash
# Test connectivity to Apple
ping apple.com

# Check if behind firewall/VPN
# Temporarily disable VPN and try again
```

#### Solution 2: Restart Xcode and Try Again

```bash
# Kill Xcode completely
killall Xcode

# Relaunch
open ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj
```

#### Solution 3: Use Application Loader (Legacy)

```bash
# For older Xcode versions
# Open Application Loader (Xcode → Open Developer Tool → Application Loader)
# Drag .ipa file to upload
```

#### Solution 4: Upload via Command Line

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean

# Export IPA
xcodebuild -exportArchive \
  -archivePath ~/Library/Developer/Xcode/Archives/[DATE]/Umuve.xcarchive \
  -exportPath ~/Desktop/Umuve-ipa \
  -exportOptionsPlist exportOptions.plist

# Upload via xcrun
xcrun altool --upload-app \
  --type ios \
  --file ~/Desktop/Umuve-ipa/Umuve.ipa \
  --username your@email.com \
  --password "app-specific-password"
```

**Create `exportOptions.plist`:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store</string>
    <key>teamID</key>
    <string>YOUR_TEAM_ID</string>
    <key>uploadSymbols</key>
    <true/>
</dict>
</plist>
```

---

### Error: "App size exceeds limit"

**Symptoms:**
```
The app size exceeds the maximum allowed size
```

**Cause:**
App binary is over 4GB (very rare).

**Solutions:**

1. **Enable App Thinning:**
   - Xcode does this by default
   - Users download only assets for their device

2. **Optimize Assets:**
   ```bash
   # Compress images
   # Remove unused assets
   # Use asset catalogs
   ```

3. **On-Demand Resources:**
   - Move large assets to on-demand resources
   - Download only when needed

---

### Error: "Invalid Swift support"

**Symptoms:**
```
Invalid Swift Support - The bundle contains an invalid implementation of Swift
```

**Cause:**
- Xcode version mismatch
- Old Swift runtime included

**Solution:**

```bash
# Update Xcode to latest version
# Clean derived data
rm -rf ~/Library/Developer/Xcode/DerivedData

# Clean project
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
xcodebuild clean -project JunkOS.xcodeproj -scheme Umuve

# Archive again
```

---

## App Store Connect Issues

### Error: "Bundle ID not found"

**Symptoms:**
```
The specified bundle identifier doesn't exist in your account
```

**Cause:**
Bundle ID in Xcode doesn't match App Store Connect.

**Solutions:**

#### Solution 1: Verify Bundle ID

**In Xcode:**
- Project → Target → General → Bundle Identifier
- Should be: `com.goumuve.app`

**In App Store Connect:**
- My Apps → Umuve → App Information
- Bundle ID should match exactly

#### Solution 2: Create App Record First

1. **Go to:** https://appstoreconnect.apple.com
2. **My Apps → +  → New App**
3. **Enter Bundle ID:** `com.goumuve.app`
4. **Create app**
5. **Then upload build**

---

### Error: "App name already exists"

**Symptoms:**
```
The app name 'Umuve' is already in use
```

**Cause:**
Another app (yours or someone else's) is using that name.

**Solutions:**

1. **Try variations:**
   - Umuve Pro
   - Umuve: Junk Removal
   - Umuve - Tampa Bay

2. **Check your other apps:**
   - You might have created it before
   - Check App Store Connect → My Apps

3. **Contact Apple Developer Support:**
   - If you believe it's your name/trademark

---

### Error: "Missing compliance information"

**Symptoms:**
- Yellow warning: "Missing Compliance"
- Build shows in TestFlight but can't add to groups

**Solution:**

1. **Click on build (1.0 - 1)**
2. **Click "Manage"** next to Missing Compliance
3. **Answer questions:**
   - **Q:** "Is your app designed to use cryptography?"
   - **A:** **NO** (for Umuve using only standard HTTPS)
4. **Auto-completes and warning disappears**

**If you answered YES:**
- You may need to file annual self-classification
- See: https://developer.apple.com/documentation/security/complying_with_encryption_export_regulations

---

## TestFlight Processing Issues

### Issue: "Build stuck in processing"

**Symptoms:**
- Build shows "Processing" for over 60 minutes
- No email from Apple

**Solutions:**

#### Solution 1: Wait Longer

- Processing usually takes 10-30 minutes
- Can take up to 2 hours in rare cases
- Check email for notifications

#### Solution 2: Check for Errors

1. **Go to:** App Store Connect → My Apps → Umuve → Activity
2. **Look for error messages**
3. **Check email** for rejection notices

#### Solution 3: Re-upload

If stuck for >3 hours:
1. **Increment build number** (from 1 to 2)
2. **Archive and upload again**

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
agvtool next-version -all
```

---

### Issue: "Build disappears from TestFlight"

**Symptoms:**
- Build shows up briefly, then vanishes
- Email says "Invalid Binary"

**Causes:**
- Missing Info.plist keys
- Invalid entitlements
- Malware detection (rare)
- Privacy violations

**Solutions:**

#### Check Email from Apple

Look for specific issues mentioned.

#### Common Issues:

**Missing Usage Descriptions:**

Check `Info.plist` contains:
```xml
<key>NSPhotoLibraryUsageDescription</key>
<string>We need access to your photo library...</string>

<key>NSCameraUsageDescription</key>
<string>We need camera access...</string>
```

**Invalid Bitcode:**
- Ensure "Enable Bitcode" is set consistently
- For iOS 14+, bitcode is optional

**Link Issues:**
- Check all frameworks are properly linked
- Remove any broken references

---

## Tester Installation Problems

### Issue: "Tester can't find invite"

**Symptoms:**
- Tester says they didn't receive email
- Can't find TestFlight invitation

**Solutions:**

#### Solution 1: Check Spam Folder

- TestFlight invites sometimes go to spam
- Email subject: "You're invited to test [AppName]"

#### Solution 2: Resend Invitation

1. **App Store Connect → TestFlight**
2. **Find tester** in your group
3. **Click "..." → Resend Invitation**

#### Solution 3: Use Public Link

1. **External Testing → Group**
2. **Enable Public Link**
3. **Copy link → Send via iMessage/WhatsApp**

---

### Issue: "TestFlight says 'not available in your region'"

**Symptoms:**
```
This beta is not available in your region
```

**Causes:**
- App not available in tester's country
- Tester's Apple ID country doesn't match

**Solutions:**

#### Solution 1: Check App Availability

1. **App Store Connect → Pricing and Availability**
2. **Select "Available in all countries"**
3. **Or add specific countries**

#### Solution 2: Tester Changes Apple ID Region

- Settings → [Name] → Media & Purchases → View Account
- Country/Region → Change Country
- Select country where app is available

---

### Issue: "Can't install - 'Unable to download'"

**Symptoms:**
```
Unable to download app
Could not download at this time
```

**Causes:**
- Storage full on device
- iOS version too old
- Build expired (90 days)

**Solutions:**

#### Check Device Storage

- Settings → General → iPhone Storage
- Free up space if needed

#### Check iOS Version

```
App requires: iOS 17.0+
Tester's device: Check Settings → General → About → Software Version
```

If too old, tester must update iOS or use different device.

#### Check Build Expiration

TestFlight builds expire after **90 days**.

1. **Check build date** in App Store Connect
2. **Upload new build if expired**

---

## Build Issues

### Error: "Build failed - no such file"

**Symptoms:**
```
error: file not found: /path/to/file.swift
```

**Cause:**
File referenced in project but deleted from disk.

**Solution:**

1. **Xcode Navigator → Find red file references**
2. **Right-click red file → Delete → Remove Reference**
3. **Clean Build Folder (⌘⇧K)**
4. **Build again**

---

### Error: "Undefined symbols for architecture arm64"

**Symptoms:**
```
Undefined symbols for architecture arm64:
  "_OBJC_CLASS_$_SomeClass", referenced from...
```

**Causes:**
- Missing framework
- Framework not linked to target
- Missing file in compile sources

**Solutions:**

#### Solution 1: Check Framework Linking

1. **Target → General → Frameworks, Libraries, and Embedded Content**
2. **Verify all needed frameworks are present**
3. **Add missing framework with "+"**

#### Solution 2: Check Compile Sources

1. **Target → Build Phases → Compile Sources**
2. **Verify all .swift files are listed**
3. **Add missing files with "+"**

---

### Error: "Module not found"

**Symptoms:**
```
error: no such module 'ModuleName'
```

**Causes:**
- Import statement for non-existent module
- Framework not added to project
- Typo in module name

**Solutions:**

1. **Check import statements** in your code
2. **Remove imports for unused modules**
3. **Add frameworks if needed:**
   - Target → General → Frameworks → "+"
   - Add PhotosUI, CoreLocation, etc.

---

## Validation Errors

### Error: "Missing required icon"

**Symptoms:**
```
Missing required icon file. The bundle does not contain an app icon for iPhone / iPod Touch of exactly '60x60' pixels
```

**Cause:**
App icon asset catalog missing sizes.

**Solution:**

1. **Assets.xcassets → AppIcon**
2. **Ensure all required sizes are filled:**
   - 20x20 (2x, 3x)
   - 29x29 (2x, 3x)
   - 40x40 (2x, 3x)
   - 60x60 (2x, 3x)
   - 1024x1024 (App Store)

**Use icon generator:**
- https://www.appicon.co/
- Upload 1024x1024 PNG → Download all sizes

---

### Error: "Invalid Info.plist"

**Symptoms:**
```
Invalid Info.plist. The Info.plist is missing required keys.
```

**Cause:**
Required keys not in Info.plist.

**Solution:**

**Check Info.plist contains:**
```xml
<key>CFBundleShortVersionString</key>
<string>1.0</string>

<key>CFBundleVersion</key>
<string>1</string>

<key>CFBundleIdentifier</key>
<string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>

<!-- Privacy keys -->
<key>NSPhotoLibraryUsageDescription</key>
<string>We need access to your photo library...</string>
```

---

### Error: "Invalid bundle structure"

**Symptoms:**
```
Invalid Bundle Structure. The binary file is not permitted.
```

**Causes:**
- Extra files in bundle
- Symbolic links
- Script files included by mistake

**Solution:**

```bash
# Check bundle contents
cd ~/Library/Developer/Xcode/Archives/.../Umuve.xcarchive
find Products/Applications/Umuve.app -type f

# Look for:
# - .sh scripts (shouldn't be there)
# - Symbolic links
# - Non-standard files
```

**Fix:**
- Clean derived data
- Remove unnecessary files from project
- Rebuild

---

## Beta Review Rejections

### Rejection: "App crashes on launch"

**Cause:**
Critical bug causing crash during Apple's review.

**Solution:**

1. **Test on fresh device:**
   - Simulators can hide issues
   - Use actual device with clean iOS install

2. **Check crash logs:**
   - TestFlight → Crashes tab
   - Fix identified issues

3. **Add crash protection:**
   ```swift
   // Wrap risky code in do-catch
   do {
       try riskyOperation()
   } catch {
       print("Error: \(error)")
       // Handle gracefully
   }
   ```

4. **Increment build and resubmit**

---

### Rejection: "Incomplete beta info"

**Cause:**
"What to Test" field is empty or unhelpful.

**Solution:**

1. **TestFlight → Test Information**
2. **Fill in "What to Test" with:**
   - What features work
   - What features are not implemented
   - Specific testing instructions
   - Known issues
3. **Add feedback email**
4. **Resubmit for review**

---

### Rejection: "Privacy policy missing or invalid"

**Cause:**
Privacy policy URL doesn't work or isn't detailed enough.

**Solution:**

1. **Verify URL works:** https://goumuve.com/privacy
   ```bash
   curl -I https://goumuve.com/privacy
   # Should return 200 OK
   ```

2. **Check policy content includes:**
   - What data you collect
   - How you use it
   - Who you share it with
   - How to contact you

3. **Update URL in:**
   - App Store Connect → App Information
   - Privacy Policy URL

---

## Crash Reports

### Reading Crash Reports

**Access crash reports:**

1. **App Store Connect → TestFlight → Crashes**
2. **Or:** Xcode → Window → Organizer → Crashes

**Example crash report:**
```
Exception Type: EXC_CRASH (SIGABRT)
Exception Codes: 0x0000000000000000, 0x0000000000000000
Crashed Thread: 0

Thread 0 Crashed:
0   libswiftCore.dylib    0x00000001a9c8b3a0 _assertionFailure
1   Umuve                0x0000000102a8c480 BookingViewModel.submitBooking()
2   Umuve                0x0000000102a8c590 closure #1 in BookingView.body
```

**Key information:**
- **Exception Type:** Type of crash
- **Crashed Thread:** Which thread crashed (0 = main)
- **Stack trace:** Shows what code was executing

---

### Common Crash Causes

#### Nil Optional Unwrapping

**Crash:**
```
Fatal error: Unexpectedly found nil while unwrapping an Optional
```

**Fix:**
```swift
// ❌ Bad
let name = user!.name

// ✅ Good
guard let user = user else { return }
let name = user.name

// Or
if let name = user?.name {
    // Use name
}
```

#### Array Index Out of Bounds

**Crash:**
```
Fatal error: Index out of range
```

**Fix:**
```swift
// ❌ Bad
let item = array[5]

// ✅ Good
guard array.indices.contains(5) else { return }
let item = array[5]

// Or
if let item = array[safe: 5] {
    // Use item
}

// Extension for safe array access
extension Array {
    subscript(safe index: Int) -> Element? {
        return indices.contains(index) ? self[index] : nil
    }
}
```

---

## General Debugging

### Enable Verbose Logging

**For uploads:**

```bash
# Set environment variable
export DEBUG=1

# Upload with verbose output
xcodebuild -verbose ...
```

---

### Check System Status

**Apple services status:**

https://developer.apple.com/system-status/

If Apple services are down:
- App Store Connect: Yellow/Red
- TestFlight: Yellow/Red

Wait and try again later.

---

### Clear Derived Data

**When things just don't make sense:**

```bash
# Clear all derived data
rm -rf ~/Library/Developer/Xcode/DerivedData

# Clear specific project
rm -rf ~/Library/Developer/Xcode/DerivedData/Umuve-*

# In Xcode
# Product → Clean Build Folder (⌘⇧K)
# Then: Product → Build (⌘B)
```

---

### Reset Xcode

**Nuclear option when Xcode is misbehaving:**

```bash
# Quit Xcode completely
killall Xcode

# Remove preferences
defaults delete com.apple.dt.Xcode

# Remove caches
rm -rf ~/Library/Caches/com.apple.dt.Xcode

# Remove derived data
rm -rf ~/Library/Developer/Xcode/DerivedData

# Restart Xcode
```

---

### Check Build Logs

**Detailed build logs:**

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean

# Build and save log
xcodebuild -project JunkOS.xcodeproj \
  -scheme Umuve \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  clean build 2>&1 | tee build.log

# Search for errors
grep -i error build.log

# Search for warnings
grep -i warning build.log
```

---

## Getting Help

### Apple Developer Forums

**Post your issue:**
https://developer.apple.com/forums/

**Include:**
- Xcode version
- macOS version
- iOS deployment target
- Full error message
- Steps to reproduce

---

### Apple Developer Support

**Contact directly:**
https://developer.apple.com/contact/

**Cases they handle:**
- Account issues
- Certificate problems
- App Store Connect bugs
- Review appeals

---

### Stack Overflow

**Search first:**
https://stackoverflow.com/questions/tagged/xcode+testflight

**When posting:**
- Include error messages
- Show relevant code
- Describe what you've tried
- Use appropriate tags: xcode, swift, testflight

---

## Quick Command Reference

```bash
# Check certificates
security find-identity -v -p codesigning

# List provisioning profiles
ls ~/Library/MobileDevice/Provisioning\ Profiles/

# Increment build number
agvtool next-version -all

# Clean build
xcodebuild clean -project JunkOS.xcodeproj -scheme Umuve

# Clear derived data
rm -rf ~/Library/Developer/Xcode/DerivedData

# Verify code signature
codesign -vv -d /path/to/Umuve.app

# Check app info
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" Umuve/Info.plist
/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" Umuve/Info.plist
```

---

## Still Stuck?

1. ✅ Check [TESTFLIGHT_SETUP_GUIDE.md](./TESTFLIGHT_SETUP_GUIDE.md)
2. ✅ Check [CODE_SIGNING_GUIDE.md](./CODE_SIGNING_GUIDE.md)
3. ✅ Search Apple Developer Forums
4. ✅ Check Stack Overflow
5. ✅ Contact Apple Developer Support
6. ✅ Email: support@goumuve.com

---

**Remember:** Most issues have been solved by someone else. Search before panicking! 🔍

**Last Updated:** February 7, 2026
