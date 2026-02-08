# JunkOS - Xcode Setup Checklist for TestFlight

**Last Updated:** February 7, 2026  
**Project Ready:** ✅ All automated configuration complete

This checklist covers the **user-performed steps** needed to archive and submit JunkOS to TestFlight.

---

## 📋 Pre-Submission Checklist

### ✅ Step 1: Add App Icon (REQUIRED)

**Status:** ⚠️ **Must Complete Before Archive**

1. **Generate Icon Assets:**
   - Use your icon generator tool to create all required sizes
   - You need a 1024x1024 master icon at minimum

2. **Add Icons to Project:**
   ```bash
   # Navigate to the AppIcon folder
   cd ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS/Assets.xcassets/AppIcon.appiconset/
   
   # Place your generated icon files here
   # Files must match names in Contents.json:
   # - AppIcon-1024x1024@1x.png (REQUIRED for App Store)
   # - AppIcon-60x60@2x.png, AppIcon-60x60@3x.png
   # - AppIcon-40x40@2x.png, AppIcon-40x40@3x.png
   # ... etc (see PROJECT_SETTINGS_REPORT.md for full list)
   ```

3. **Verify in Xcode:**
   - Open project in Xcode
   - Navigate to: `JunkOS` target → `General` tab
   - Scroll to `App Icons and Launch Screen`
   - **All icon slots should be filled** (no missing icon warnings)

---

### ✅ Step 2: Configure Code Signing

**Status:** ⚠️ **User Must Select Team**

1. **Open Project in Xcode:**
   ```bash
   open ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj
   ```

2. **Select Your Team:**
   - Click on `JunkOS` project in the Navigator (top of file list)
   - Select `JunkOS` target under `TARGETS`
   - Go to `Signing & Capabilities` tab
   - Under **Team**: Select your Apple Developer team from dropdown
   - Xcode should automatically manage provisioning profiles

3. **Verify Signing:**
   - ✅ No red errors should appear
   - ✅ "Provisioning Profile" should show automatic profile
   - ✅ "Signing Certificate" should show your development/distribution cert

4. **Troubleshooting Signing Issues:**
   - If you see "Failed to create provisioning profile":
     - Verify your Apple ID is signed in: `Xcode` → `Settings` → `Accounts`
     - Ensure you have an active Apple Developer Program membership
     - Try clicking "Download Manual Profiles" in Accounts
   
   - If Bundle ID conflicts exist:
     - Go to [Apple Developer Portal](https://developer.apple.com/account)
     - Check `Certificates, Identifiers & Profiles` → `Identifiers`
     - Verify `com.junkos.app` is available or registered to your team

---

### ✅ Step 3: Build Verification (Optional but Recommended)

**Test that the project builds before archiving:**

1. **Select a Real Device or Any iOS Device:**
   - In Xcode toolbar, click the device selector (next to scheme)
   - Choose `Any iOS Device (arm64)` for archive
   - OR connect a physical iPhone/iPad and select it

2. **Build the Project:**
   - Press `⌘ + B` (Command + B)
   - OR: `Product` → `Build`
   - **Expected:** Build Succeeded ✅
   - **If errors occur:** Review build log and resolve before proceeding

---

## 🚀 Archiving for TestFlight

### Step 4: Create Archive

1. **Select Build Scheme:**
   - Ensure `JunkOS` scheme is selected in toolbar
   - Select `Any iOS Device (arm64)` as destination

2. **Archive the App:**
   - Go to: `Product` → `Archive`
   - OR: Press `⌘ + Control + A`
   - Wait for archive process to complete (may take 1-3 minutes)

3. **Archive Success:**
   - Xcode Organizer window will open automatically
   - Your archive should appear in the list with today's date

---

### Step 5: Validate Archive (Recommended)

**Before submitting, validate the archive for common issues:**

1. **In Xcode Organizer:**
   - Select your archive
   - Click **"Validate App"** button

2. **Validation Options:**
   - **App Store Connect distribution:** Yes
   - **Upload symbols:** Yes (recommended for crash reports)
   - **Manage Version and Build Number:** Automatic (default)

3. **Review Validation Results:**
   - ✅ **No issues:** Proceed to submission
   - ⚠️ **Warnings:** Review but usually safe to proceed
   - ❌ **Errors:** Must fix before submission

**Common Issues:**
- **Missing Export Compliance:** You may need to declare if app uses encryption
- **Missing Icons:** Go back to Step 1
- **Invalid Bundle ID:** Check that `com.junkos.app` is registered

---

### Step 6: Distribute to TestFlight

1. **In Xcode Organizer:**
   - Select your validated archive
   - Click **"Distribute App"** button

2. **Distribution Method:**
   - Select: **"TestFlight & App Store"**
   - Click `Next`

3. **Distribution Options:**
   - **Destination:** App Store Connect
   - **Upload symbols:** ✅ Yes
   - **Manage version automatically:** ✅ Yes
   - Click `Next`

4. **Signing:**
   - **Automatically manage signing:** ✅ Yes (recommended)
   - Click `Next`
   - Review signing summary → `Upload`

5. **Upload Progress:**
   - Xcode will prepare and upload your archive
   - Wait for "Upload Successful" message
   - This can take 5-15 minutes depending on file size and connection

---

## 🎯 Post-Upload Steps

### Step 7: App Store Connect Configuration

1. **Log in to App Store Connect:**
   - Go to: [https://appstoreconnect.apple.com](https://appstoreconnect.apple.com)
   - Sign in with your Apple ID

2. **Find Your App:**
   - Click `My Apps`
   - Find `JunkOS` (or create new app if first time)

3. **Wait for Build Processing:**
   - Your uploaded build will appear under `TestFlight` → `Builds`
   - Status will show "Processing" for 5-30 minutes
   - You'll receive email when processing completes

4. **Add Testing Information:**
   - Go to `TestFlight` → `Test Information`
   - Fill in required fields:
     - **Beta App Description:** Short description for testers
     - **Feedback Email:** Your email for tester feedback
     - **Test Information:** What you want testers to focus on

5. **Export Compliance (If Prompted):**
   - If your app uses HTTPS/encryption, you may need to answer questions
   - For most apps: `No` to ITAR, `No` to custom encryption

---

### Step 8: Invite Testers

**Internal Testing (Instant):**
1. Go to `TestFlight` → `Internal Testing`
2. Create an internal group (or use default)
3. Add Apple IDs of your team members
4. Build will be available immediately after processing

**External Testing (Requires Review):**
1. Go to `TestFlight` → `External Testing`
2. Create a test group
3. Add testers by email
4. Submit for Beta App Review (usually approved within 24 hours)
5. Once approved, testers receive email with TestFlight link

---

## ✅ Final Verification Checklist

Before hitting "Upload":

- [ ] App icon is present and visible in Xcode (all sizes)
- [ ] Development team is selected in project settings
- [ ] No signing errors in `Signing & Capabilities` tab
- [ ] Project builds successfully (`⌘ + B`)
- [ ] Archive created successfully
- [ ] Archive validated without critical errors
- [ ] Ready to upload to App Store Connect

---

## 🐛 Troubleshooting Common Issues

### "No signing certificate found"
- **Fix:** Xcode → Settings → Accounts → Download Manual Profiles
- **Or:** Let Xcode automatically create a certificate (first-time setup)

### "Provisioning profile doesn't include signing certificate"
- **Fix:** Delete derived data: `Xcode` → `Settings` → `Locations` → click arrow next to Derived Data → Delete folder
- **Then:** Clean build folder (`⌘ + Shift + K`) and re-archive

### "App icon not found"
- **Fix:** Verify icon files are physically present in `Assets.xcassets/AppIcon.appiconset/`
- **Check:** Filenames match exactly with `Contents.json`
- **Ensure:** 1024x1024 marketing icon is present

### "Build number already in use"
- **Fix:** Increment `CURRENT_PROJECT_VERSION` in project settings
- **Or:** Use a unique build number format like `1.1`, `1.2`, etc.

### Archive upload fails
- **Check:** Internet connection is stable
- **Try:** Upload later (App Store Connect may have temporary issues)
- **Verify:** Your Apple Developer Program membership is active

---

## 📚 Additional Resources

- [Apple TestFlight Beta Testing Guide](https://developer.apple.com/testflight/)
- [App Store Connect Help](https://help.apple.com/app-store-connect/)
- [Code Signing Guide](https://developer.apple.com/support/code-signing/)

---

## 🎉 Success!

Once your build is uploaded and processed:
- ✅ Appears in App Store Connect → TestFlight
- ✅ Can be distributed to internal testers immediately
- ✅ Can be submitted for external beta review
- ✅ Ready for App Store submission when ready

---

**Good luck with your TestFlight submission! 🚀**
